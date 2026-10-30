"""Entry point for reviewed Alembic migrations, independent of server startup."""


def upgrade_database(connection):
    from pathlib import Path
    from alembic.config import Config
    from alembic import command
    root=Path(__file__).resolve().parents[2]
    config=Config(str(root/'alembic.ini'))
    config.set_main_option('script_location',str(root/'migrations'))
    config.attributes['connection']=connection
    command.upgrade(config,'head')
