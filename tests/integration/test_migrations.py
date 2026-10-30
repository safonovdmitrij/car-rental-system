"""Migration bootstrap: empty dedicated PostgreSQL schema and real business read.
This verifies deployment infrastructure, not a new functional requirement.
"""
from uuid import uuid4
from pathlib import Path
from sqlalchemy import create_engine,text,inspect
from car_rental.migrations import upgrade_database


def test_empty_database_upgrade_is_repeatable_and_preserves_data():
    url='postgresql+psycopg://car_rental_test@127.0.0.1:55432/postgres'
    admin=create_engine(url);schema='migration_'+uuid4().hex
    with admin.connect() as c:
        assert Path(c.scalar(text('SHOW data_directory'))).resolve()==Path('.backend-setup/postgres-test').resolve()
    with admin.begin() as c:c.execute(text('CREATE SCHEMA "'+schema+'"'))
    engine=create_engine(url,connect_args={'options':'-csearch_path='+schema})
    try:
        with engine.begin() as c:upgrade_database(c)
        assert set(inspect(engine).get_table_names())=={'alembic_version','accounts','cars','occupations','login_sessions','quotes','bookings','service_periods'}
        with engine.begin() as c:
            c.execute(text("INSERT INTO cars(id,characteristics,daily_rate,hidden,rate_version) VALUES ('preserved','{\"model\":\"Sport\"}','1500.00',false,0)"))
            upgrade_database(c)
            assert c.scalar(text('SELECT COUNT(*) FROM cars'))==1
    finally:
        engine.dispose()
        with admin.begin() as c:c.execute(text('DROP SCHEMA "'+schema+'" CASCADE'))
        admin.dispose()
