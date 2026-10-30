"""Independent time/state rules; persistence and HTTP commands are separate."""
from datetime import datetime,timezone
from car_rental.availability import cancellation_deadline
from car_rental.calendar import parse_local_hour


def booking_status(start:datetime,end:datetime,*,cancelled:bool,now:datetime)->str:
    if cancelled:
        return 'cancelled'
    instant=now.astimezone(timezone.utc)
    if instant>=end.astimezone(timezone.utc):return 'completed'
    if instant>=start.astimezone(timezone.utc):return 'active'
    return 'confirmed'


def check_cancellation(role:str,*,owns:bool,start:datetime,end:datetime,cancelled:bool,now:datetime,reason:str|None=None)->None:
    if role not in ('client','administrator') or (role=='client' and not owns):
        raise ValueError('FORBIDDEN')
    if cancelled:raise ValueError('ALREADY_CANCELLED')
    if booking_status(start,end,cancelled=False,now=now)!='confirmed':raise ValueError('BOOKING_NOT_CANCELLABLE')
    if role=='administrator':
        if not isinstance(reason,str) or not reason.strip():raise ValueError('VALIDATION_ERROR')
    else:
        if reason is not None:raise ValueError('VALIDATION_ERROR')
        if now.astimezone(timezone.utc)>cancellation_deadline(start).astimezone(timezone.utc):
            raise ValueError('CANCELLATION_DEADLINE_PASSED')


def check_service_period(start:str,end:str,*,now:datetime,previous_start:datetime|None=None)->tuple[datetime,datetime]:
    instant=now.astimezone(timezone.utc)
    if previous_start is not None and previous_start.astimezone(timezone.utc)<=instant:
        raise ValueError('SERVICE_PERIOD_ALREADY_STARTED')
    a,b=parse_local_hour(start),parse_local_hour(end)
    if a.astimezone(timezone.utc)<=instant or b.astimezone(timezone.utc)<=a.astimezone(timezone.utc):
        raise ValueError('VALIDATION_ERROR')
    return a,b
