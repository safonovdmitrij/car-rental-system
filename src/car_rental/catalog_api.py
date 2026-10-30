"""Public catalog ASGI factory; target behavior introduced after its RED."""
import sys
from datetime import datetime,timezone
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session
from car_rental.availability import overlaps
from car_rental.calendar import parse_local_hour
from car_rental.storage import Car, Occupation
from car_rental.observability import JsonEventLogger, RequestLoggingMiddleware


class ApiFailure(Exception):
    def __init__(self, status, code, details=None,headers=None):
        self.status, self.code, self.details = status, code, details or {}
        self.headers=headers or {}


def invalid(field):
    raise ApiFailure(422,"VALIDATION_ERROR",{"fields":[{"field":field,"message":"Некоректне значення."}]})


def period(request, required):
    if set(request.query_params)-{"startsAt","endsAt"}:
        invalid("query")
    a,b=request.query_params.get("startsAt"),request.query_params.get("endsAt")
    if a is None and b is None and not required:
        return None
    if a is None or b is None:
        invalid("period")
    try:
        start,end=parse_local_hour(a),parse_local_hour(b)
        if end <= start:
            invalid("period")
    except ValueError:
        invalid("period")
    return start,end


def public(car):
    return {"id":car.id,"characteristics":car.characteristics,"dailyRate":car.daily_rate,"currency":"UAH"}


def available(session, car, bounds,now=None):
    if car.hidden:
        return False
    instant=now or datetime.now(timezone.utc)
    return not any(overlaps(*bounds,entry.starts_at,entry.ends_at) for entry in session.scalars(
        select(Occupation).where(Occupation.car_id==car.id,Occupation.kind.in_(["confirmed","active","service","booking"]))
    ) if entry.kind!='booking' or entry.ends_at>instant)


def create_catalog_app(engine,event_stream=None):
    app=FastAPI(openapi_url=None,docs_url=None,redoc_url=None)
    app.add_middleware(RequestLoggingMiddleware,logger=JsonEventLogger(event_stream if event_stream is not None else sys.stdout))

    @app.exception_handler(ApiFailure)
    async def failure(request, error):
        message="Ресурс не знайдено." if error.code=="NOT_FOUND" else "Операцію не виконано."
        return JSONResponse({"error":{"code":error.code,"message":message,"details":error.details}},status_code=error.status,headers=error.headers)

    @app.exception_handler(HTTPException)
    async def http_failure(request,error):
        code="METHOD_NOT_ALLOWED" if error.status_code==405 else "NOT_FOUND"
        result=await failure(request,ApiFailure(error.status_code,code))
        if error.headers:
            result.headers.update(error.headers)
        if error.status_code==405:
            methods=set()
            for route in app.routes:
                matcher=getattr(route,'path_regex',None)
                if matcher is not None and matcher.fullmatch(request.url.path):methods.update(route.methods)
            result.headers['Allow']=', '.join(method for method in ('GET','POST','PUT','PATCH','DELETE','OPTIONS','HEAD','TRACE') if method in methods)
        return result

    @app.exception_handler(OperationalError)
    async def unavailable(request,error):
        return await failure(request,ApiFailure(503,'SERVICE_UNAVAILABLE'))

    @app.exception_handler(Exception)
    async def unexpected(request,error):
        return await failure(request,ApiFailure(500,'INTERNAL_ERROR'))

    def session():
        if engine is None:
            raise ApiFailure(503,"SERVICE_UNAVAILABLE")
        return Session(engine)

    def projection(s,car,request):
        renderer=getattr(app.state,'project_car',None)
        return renderer(s,car,request) if renderer else public(car)

    @app.get("/api/v1/cars")
    async def cars(request: Request):
        bounds=period(request,False)
        with session() as s:
            return {"items":[projection(s,car,request) for car in s.scalars(select(Car).where(Car.hidden==False))
                             if bounds is None or available(s,car,bounds,getattr(app.state,'now',lambda:datetime.now(timezone.utc))())]}

    @app.get("/api/v1/cars/{car_id}")
    async def details(car_id:str,request:Request):
        with session() as s:
            car=s.get(Car,car_id)
            if car is None:
                raise ApiFailure(404,"NOT_FOUND")
            result=projection(s,car,request)
            if car.hidden and 'hidden' not in result:raise ApiFailure(404,"NOT_FOUND")
            return result

    @app.get("/api/v1/cars/{car_id}/availability")
    async def availability(car_id:str,request:Request):
        bounds=period(request,True)
        with session() as s:
            car=s.get(Car,car_id)
            if car is None:
                raise ApiFailure(404,"NOT_FOUND")
            return {"carId":car.id,"startsAt":request.query_params['startsAt'],"endsAt":request.query_params['endsAt'],
                    "timezone":"Europe/Kyiv","available":available(s,car,bounds,getattr(app.state,'now',lambda:datetime.now(timezone.utc))())}
    return app
