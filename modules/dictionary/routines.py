async def save_changes_on_disk(app, session):
    if app['autocommit']:
        session.commit()
        session.flush()