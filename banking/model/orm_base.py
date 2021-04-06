from sqlalchemy.orm import registry

mapper_registry = registry()


def set_up_orm(engine):
    mapper_registry.metadata.create_all(engine)
