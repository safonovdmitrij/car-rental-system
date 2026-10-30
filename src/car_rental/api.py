"""ASGI factory extended through package TDD cycles."""
from datetime import datetime,timezone,timedelta
from hashlib import sha256
import secrets
import sys
from math import ceil
from uuid import uuid4
from argon2 import PasswordHasher
from argon2.exceptions import VerificationError
from fastapi import Request,Response
from fastapi.responses import JSONResponse
from sqlalchemy import select,update,func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from car_rental.catalog_api import ApiFailure,create_catalog_app,invalid
from car_rental.storage import Account,LoginSession,Car,Occupation,QuoteRecord,Booking,ServicePeriod
from car_rental.catalog_api import public,available
from car_rental.calendar import validate_rental,KYIV
from car_rental.pricing import billable_days,total_price
from car_rental.booking_rules import booking_status,check_service_period,check_cancellation
from car_rental.availability import cancellation_deadline,overlaps
from car_rental.observability import JsonEventLogger
from car_rental.contract import operation,dereference,valid


PASSWORDS=PasswordHasher(memory_cost=19456,time_cost=2,parallelism=1)


def token_digest(token):
    return sha256(token.encode()).hexdigest()


def local_hour(value):
    return value.astimezone(KYIV).strftime('%Y-%m-%dT%H')


async def body(request,allowed,required=()):
    try:
        data=await request.json()
    except (ValueError,UnicodeError):raise ApiFailure(400,'BAD_REQUEST')
    if not isinstance(data,dict) or set(data)-set(allowed) or set(required)-set(data):invalid('request')
    if isinstance(data.get('email'),str):data['email']=data['email'].strip()
    op=operation(request.method,request.url.path)
    if op and 'requestBody' in op:
        schema=dereference(op['requestBody'])['content']['application/json']['schema']
        if not valid(schema,data):invalid('request')
    return data


def nonblank(value):return isinstance(value,str) and bool(value.strip())


def profile(account):
    return {'clientId':account.id,'firstName':account.first_name,'lastName':account.last_name,'email':account.email,'phone':account.phone}


def authenticate(session,request,now,roles=('client','administrator')):
    header=request.headers.get('authorization','')
    entry=session.get(LoginSession,token_digest(header[7:])) if header.startswith('Bearer ') else None
    if entry is None or entry.revoked or now.astimezone(timezone.utc)>=entry.created_at.astimezone(timezone.utc)+timedelta(seconds=86400):
        raise ApiFailure(401,'AUTHENTICATION_REQUIRED',headers={'WWW-Authenticate':'Bearer'})
    account=session.get(Account,entry.account_id)
    if account is None:raise ApiFailure(401,'AUTHENTICATION_REQUIRED',headers={'WWW-Authenticate':'Bearer'})
    if account.role not in roles:raise ApiFailure(403,'FORBIDDEN')
    return account


def booking_view(s,booking,viewer,now):
    car=s.get(Car,booking.car_id)
    cancellation=None
    if booking.cancelled:
        cancellation={'cancelledAt':booking.cancelled_at.isoformat(),'authorRole':booking.author_role,'reason':booking.reason}
        if viewer.role=='administrator':cancellation['authorAccountId']=booking.author_id
    result={'id':booking.id,'car':{'id':car.id,'characteristics':car.characteristics},
            'startsAt':local_hour(booking.starts_at),
            'endsAt':local_hour(booking.ends_at),'timezone':'Europe/Kyiv',
            'status':booking_status(booking.starts_at,booking.ends_at,cancelled=booking.cancelled,now=now),
            'dailyRate':booking.daily_rate,'billableDays':booking.days,'totalPrice':booking.total,'currency':'UAH',
            'clientCancellationDeadline':cancellation_deadline(booking.starts_at).isoformat(),'cancellation':cancellation}
    if viewer.role=='administrator':result['client']=profile(s.get(Account,booking.account_id))
    return result


def create_app(engine,now=None,event_stream=None):
    app=create_catalog_app(engine,event_stream)
    app.state.now=now or (lambda:datetime.now(timezone.utc))

    def audit(event,result='success'):
        JsonEventLogger(sys.stdout).emit(event,result)
        if event_stream is not None:JsonEventLogger(event_stream).emit(event,result)

    def admin_car(s,car):
        count=s.scalar(select(func.count()).select_from(Occupation).where(Occupation.car_id==car.id,Occupation.kind.in_(['confirmed','booking']),Occupation.starts_at>app.state.now()))
        return {**public(car),'hidden':car.hidden,'futureBookingsCount':count}

    def project_car(s,car,request):
        try:account=authenticate(s,request,app.state.now())
        except ApiFailure:return public(car)
        return admin_car(s,car) if account.role=='administrator' else public(car)
    app.state.project_car=project_car

    def quote(s,account,car,start,end):
        token=secrets.token_urlsafe(32)
        days=billable_days(start,end)
        total=total_price(car.daily_rate,days)
        s.add(QuoteRecord(token_hash=token_digest(token),account_id=account.id,car_id=car.id,starts_at=start,ends_at=end,rate_version=car.rate_version,daily_rate=car.daily_rate,days=days,total=total))
        return {'carId':car.id,'startsAt':local_hour(start),'endsAt':local_hour(end),'timezone':'Europe/Kyiv','dailyRate':car.daily_rate,'billableDays':days,'totalPrice':total,'currency':'UAH','priceConfirmationToken':token}

    @app.post('/api/v1/booking-quotes')
    async def calculate_quote(request:Request):
        with Session(engine) as s:
            account=authenticate(s,request,app.state.now(),('client',))
            data=await body(request,('carId','startsAt','endsAt'),('carId','startsAt','endsAt'))
            try:start,end=validate_rental(data['startsAt'],data['endsAt'],now=app.state.now())
            except ValueError:invalid('period')
            car=s.get(Car,data['carId'])
            if car is None:raise ApiFailure(404,'NOT_FOUND')
            if not available(s,car,(start,end),app.state.now()):raise ApiFailure(409,'CAR_UNAVAILABLE')
            result=quote(s,account,car,start,end)
            s.commit()
            audit('quote.created')
            return result

    @app.post('/api/v1/bookings',status_code=201)
    async def create_booking(request:Request):
        with Session(engine) as s:
            account=authenticate(s,request,app.state.now(),('client',))
            data=await body(request,('carId','startsAt','endsAt','priceConfirmationToken'),('carId','startsAt','endsAt','priceConfirmationToken'))
            car=s.scalar(select(Car).where(Car.id==data['carId']).with_for_update())
            if car is None:raise ApiFailure(404,'NOT_FOUND')
            try:start,end=validate_rental(data['startsAt'],data['endsAt'],now=app.state.now())
            except ValueError:invalid('period')
            quoted=s.get(QuoteRecord,token_digest(data['priceConfirmationToken']))
            if quoted is None or (quoted.account_id,quoted.car_id,quoted.starts_at,quoted.ends_at)!=(account.id,car.id,start,end):invalid('priceConfirmationToken')
            if not available(s,car,(start,end),app.state.now()):raise ApiFailure(409,'CAR_UNAVAILABLE')
            if quoted.rate_version!=car.rate_version:
                revised=quote(s,account,car,start,end);s.commit()
                audit('quote.price_changed','error')
                raise ApiFailure(409,'PRICE_CHANGED',{'quote':revised})
            booking=Booking(id=uuid4().hex,car_id=car.id,account_id=account.id,starts_at=start,ends_at=end,daily_rate=quoted.daily_rate,days=quoted.days,total=quoted.total,cancelled=False)
            s.add(booking)
            s.add(Occupation(id=booking.id,car_id=car.id,starts_at=start,ends_at=end,kind='booking'))
            s.commit()
            audit('booking.created')
            return JSONResponse(booking_view(s,booking,account,app.state.now()),status_code=201,headers={'Location':'/api/v1/bookings/'+booking.id})

    @app.get('/api/v1/bookings')
    async def list_bookings(request:Request):
        with Session(engine) as s:
            account=authenticate(s,request,app.state.now())
            query=select(Booking)
            if account.role=='client':query=query.where(Booking.account_id==account.id)
            return {'items':[booking_view(s,b,account,app.state.now()) for b in s.scalars(query)]}

    @app.get('/api/v1/bookings/{booking_id}')
    async def get_booking(booking_id:str,request:Request):
        with Session(engine) as s:
            account=authenticate(s,request,app.state.now())
            booking=s.get(Booking,booking_id)
            if booking is None or (account.role=='client' and booking.account_id!=account.id):raise ApiFailure(404,'NOT_FOUND')
            return booking_view(s,booking,account,app.state.now())

    @app.post('/api/v1/bookings/{booking_id}/cancellation',status_code=201)
    async def cancel_booking(booking_id:str,request:Request):
        with Session(engine) as s:
            account=authenticate(s,request,app.state.now())
            booking=s.get(Booking,booking_id)
            if booking is None or (account.role=='client' and booking.account_id!=account.id):raise ApiFailure(404,'NOT_FOUND')
            s.scalar(select(Car).where(Car.id==booking.car_id).with_for_update())
            s.refresh(booking)
            raw=await request.body()
            data=await body(request,('reason',)) if raw else {}
            try:check_cancellation(account.role,owns=booking.account_id==account.id,start=booking.starts_at,end=booking.ends_at,cancelled=booking.cancelled,now=app.state.now(),reason=data.get('reason'))
            except ValueError as failure:
                code=str(failure)
                if code=='VALIDATION_ERROR':invalid('reason')
                raise ApiFailure(409,code)
            booking.cancelled=True;booking.cancelled_at=app.state.now();booking.author_id=account.id;booking.author_role=account.role;booking.reason=data.get('reason')
            s.get(Occupation,booking.id).kind='cancelled'
            s.commit()
            audit('booking.cancelled')
            return JSONResponse(booking_view(s,booking,account,app.state.now())['cancellation'],status_code=201,headers={'Location':'/api/v1/bookings/'+booking.id+'/cancellation'})

    def service_view(record):
        return {'id':record.id,'carId':record.car_id,'startsAt':local_hour(record.starts_at),
                'endsAt':local_hour(record.ends_at),'timezone':'Europe/Kyiv','reason':record.reason}

    def service_car(s,request,car_id,lock=False):
        authenticate(s,request,app.state.now(),('administrator',))
        query=select(Car).where(Car.id==car_id)
        car=s.scalar(query.with_for_update() if lock else query)
        if car is None:raise ApiFailure(404,'NOT_FOUND')
        return car

    def get_service(s,car_id,period_id):
        record=s.get(ServicePeriod,period_id)
        if record is None or record.car_id!=car_id:raise ApiFailure(404,'NOT_FOUND')
        return record

    def check_conflicts(s,car_id,start,end,exclude=None):
        for span in s.scalars(select(Occupation).where(Occupation.car_id==car_id)):
            if span.id==exclude or span.kind in ('cancelled','completed'):continue
            if span.kind=='booking' and span.ends_at<=app.state.now():continue
            if overlaps(start,end,span.starts_at,span.ends_at):raise ApiFailure(409,'SERVICE_PERIOD_CONFLICT')

    @app.get('/api/v1/cars/{car_id}/service-unavailabilities')
    async def services(car_id:str,request:Request):
        with Session(engine) as s:
            service_car(s,request,car_id)
            return {'items':[service_view(p) for p in s.scalars(select(ServicePeriod).where(ServicePeriod.car_id==car_id))]}

    @app.get('/api/v1/cars/{car_id}/service-unavailabilities/{period_id}')
    async def service_details(car_id:str,period_id:str,request:Request):
        with Session(engine) as s:
            service_car(s,request,car_id)
            return service_view(get_service(s,car_id,period_id))

    @app.post('/api/v1/cars/{car_id}/service-unavailabilities',status_code=201)
    async def create_service(car_id:str,request:Request):
        with Session(engine) as s:
            service_car(s,request,car_id,True)
            data=await body(request,('startsAt','endsAt','reason'),('startsAt','endsAt','reason'))
            try:start,end=check_service_period(data['startsAt'],data['endsAt'],now=app.state.now())
            except ValueError:invalid('period')
            check_conflicts(s,car_id,start,end)
            record=ServicePeriod(id=uuid4().hex,car_id=car_id,starts_at=start,ends_at=end,reason=data['reason'])
            s.add(record);s.add(Occupation(id=record.id,car_id=car_id,starts_at=start,ends_at=end,kind='service'));s.commit()
            audit('service.created')
            return JSONResponse(service_view(record),status_code=201,headers={'Location':f'/api/v1/cars/{car_id}/service-unavailabilities/{record.id}'})

    @app.patch('/api/v1/cars/{car_id}/service-unavailabilities/{period_id}')
    async def patch_service(car_id:str,period_id:str,request:Request):
        with Session(engine) as s:
            service_car(s,request,car_id,True)
            record=get_service(s,car_id,period_id)
            if record.starts_at<=app.state.now():raise ApiFailure(409,'SERVICE_PERIOD_ALREADY_STARTED')
            data=await body(request,('startsAt','endsAt','reason'))
            before=service_view(record)
            try:start,end=check_service_period(data.get('startsAt',before['startsAt']),data.get('endsAt',before['endsAt']),now=app.state.now(),previous_start=record.starts_at)
            except ValueError:invalid('period')
            check_conflicts(s,car_id,start,end,period_id)
            record.starts_at=start;record.ends_at=end;record.reason=data.get('reason',record.reason)
            span=s.get(Occupation,period_id);span.starts_at=start;span.ends_at=end
            s.commit();audit('service.updated');return service_view(record)

    @app.delete('/api/v1/cars/{car_id}/service-unavailabilities/{period_id}',status_code=204)
    async def delete_service(car_id:str,period_id:str,request:Request):
        with Session(engine) as s:
            service_car(s,request,car_id,True)
            record=get_service(s,car_id,period_id)
            if record.starts_at<=app.state.now():raise ApiFailure(409,'SERVICE_PERIOD_ALREADY_STARTED')
            s.delete(s.get(Occupation,period_id));s.delete(record);s.commit()
            audit('service.deleted')
            return Response(status_code=204)

    @app.get('/api/v1/admin/cars')
    async def fleet(request:Request):
        with Session(engine) as s:
            authenticate(s,request,app.state.now(),('administrator',))
            return {'items':[admin_car(s,car) for car in s.scalars(select(Car))]}

    @app.post('/api/v1/cars',status_code=201)
    async def create_car(request:Request):
        with Session(engine) as s:
            authenticate(s,request,app.state.now(),('administrator',))
            data=await body(request,('characteristics','dailyRate','hidden'),('characteristics','dailyRate'))
            car=Car(id=uuid4().hex,characteristics=data['characteristics'],daily_rate=data['dailyRate'],hidden=data.get('hidden',False))
            s.add(car);s.commit()
            audit('car.created')
            return JSONResponse(admin_car(s,car),status_code=201,headers={'Location':'/api/v1/cars/'+car.id})

    @app.patch('/api/v1/cars/{car_id}')
    async def patch_car(car_id:str,request:Request):
        with Session(engine) as s:
            authenticate(s,request,app.state.now(),('administrator',))
            car=s.scalar(select(Car).where(Car.id==car_id).with_for_update())
            if car is None:raise ApiFailure(404,'NOT_FOUND')
            data=await body(request,('characteristics','dailyRate','hidden'))
            if not data:invalid('request')
            if 'characteristics' in data:car.characteristics=data['characteristics']
            if 'dailyRate' in data and data['dailyRate']!=car.daily_rate:
                car.daily_rate=data['dailyRate'];car.rate_version+=1
            if 'hidden' in data:car.hidden=data['hidden']
            s.commit()
            audit('car.updated')
            projected=admin_car(s,car)
            warning=[{'code':'FUTURE_BOOKINGS_EXIST','futureBookingsCount':projected['futureBookingsCount']}] if data.get('hidden') and projected['futureBookingsCount'] else []
            return {'car':projected,'warnings':warning}

    @app.delete('/api/v1/cars/{car_id}',status_code=204)
    async def delete_car(car_id:str,request:Request):
        with Session(engine) as s:
            authenticate(s,request,app.state.now(),('administrator',))
            car=s.scalar(select(Car).where(Car.id==car_id).with_for_update())
            if car is None:raise ApiFailure(404,'NOT_FOUND')
            if s.scalar(select(Occupation.id).where(Occupation.car_id==car_id).limit(1)) is not None:raise ApiFailure(409,'CAR_HAS_RELATED_RECORDS')
            s.delete(car);s.commit()
            audit('car.deleted')
            return Response(status_code=204)

    @app.get('/api/v1/profile')
    async def own_profile(request:Request):
        with Session(engine) as s:return profile(authenticate(s,request,app.state.now(),('client',)))

    @app.patch('/api/v1/profile')
    async def patch_profile(request:Request):
        with Session(engine) as s:
            account=authenticate(s,request,app.state.now(),('client',))
            data=await body(request,('firstName','lastName','phone'))
            if not data:invalid('request')
            for key,column in [('firstName','first_name'),('lastName','last_name'),('phone','phone')]:
                if key in data:
                    if not nonblank(data[key]):invalid(key)
                    setattr(account,column,data[key])
            s.commit()
            audit('profile.updated')
            return profile(account)

    @app.put('/api/v1/profile/password',status_code=204)
    async def password_change(request:Request):
        with Session(engine) as s:
            account=authenticate(s,request,app.state.now(),('client',))
            account=s.scalar(select(Account).where(Account.id==account.id).with_for_update())
            data=await body(request,('currentPassword','newPassword'),('currentPassword','newPassword'))
            try:correct=PASSWORDS.verify(account.password_hash,data['currentPassword'])
            except VerificationError:correct=False
            if not correct:invalid('currentPassword')
            account.password_hash=PASSWORDS.hash(data['newPassword'])
            s.execute(update(LoginSession).where(LoginSession.account_id==account.id).values(revoked=True))
            s.commit()
            audit('password.changed')
            return Response(status_code=204)

    @app.post('/api/v1/clients',status_code=201)
    async def register(request:Request):
        data=await body(request,('firstName','lastName','phone','email','password'),('firstName','lastName','phone','email','password'))
        if any(not nonblank(data[k]) for k in ('firstName','lastName','phone')):invalid('profile')
        if not isinstance(data['password'],str) or len(data['password'])<8:invalid('password')
        email=data['email'].strip() if isinstance(data['email'],str) else ''
        if '@' not in email or any(c.isspace() for c in email) or not all(email.split('@')):invalid('email')
        with Session(engine) as s:
            account=Account(id=uuid4().hex,email=email,email_key=email.casefold(),first_name=data['firstName'],last_name=data['lastName'],phone=data['phone'],password_hash=PASSWORDS.hash(data['password']),role='client')
            s.add(account)
            try:s.commit()
            except IntegrityError:raise ApiFailure(409,'EMAIL_ALREADY_EXISTS')
            audit('account.created')
            return {'profile':profile(account),'role':'client'}

    @app.post('/api/v1/sessions',status_code=201)
    async def login(request:Request):
        data=await body(request,('email','password'),('email','password'))
        if not isinstance(data['email'],str) or not isinstance(data['password'],str):invalid('credentials')
        with Session(engine) as s:
            account=s.scalar(select(Account).where(Account.email_key==data['email'].strip().casefold()).with_for_update())
            instant=app.state.now()
            if account is not None and account.blocked_until is not None:
                remaining=(account.blocked_until-instant).total_seconds()
                if remaining>0:
                    audit('login.blocked','error')
                    raise ApiFailure(429,'LOGIN_BLOCKED',headers={'Retry-After':str(ceil(remaining))})
                account.failed_attempts=0
                account.blocked_until=None
            valid=False
            if account is not None:
                try:valid=PASSWORDS.verify(account.password_hash,data['password'])
                except VerificationError:pass
            if not valid:
                if account is not None:
                    account.failed_attempts+=1
                    if account.failed_attempts>=5:account.blocked_until=instant+timedelta(minutes=15)
                    s.commit()
                    if account.blocked_until is not None:
                        audit('login.blocked','error')
                        raise ApiFailure(429,'LOGIN_BLOCKED',headers={'Retry-After':'900'})
                audit('login.failed','error')
                raise ApiFailure(401,'INVALID_CREDENTIALS')
            account.failed_attempts=0
            account.blocked_until=None
            token=secrets.token_urlsafe(32)
            s.add(LoginSession(token_hash=token_digest(token),account_id=account.id,created_at=app.state.now(),revoked=False))
            s.commit()
            audit('session.created')
            return {'accessToken':token,'tokenType':'Bearer','accountId':account.id,'role':account.role}
    return app
