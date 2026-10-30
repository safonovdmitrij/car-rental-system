"""No credentials in configuration or logs; explicit DATABASE_URL for CLI."""
import os
from alembic import context
from sqlalchemy import create_engine
from car_rental.storage import Base


def run(connection):
    context.configure(connection=connection,target_metadata=Base.metadata)
    with context.begin_transaction():context.run_migrations()


provided=context.config.attributes.get('connection')
if provided is not None:
    run(provided)
else:
    engine=create_engine(os.environ['DATABASE_URL'])
    with engine.begin() as connection:run(connection)
    engine.dispose()
