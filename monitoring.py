"""
Periodic cron script to monitor recurrent tasks.
"""
from api.monitoring import MonitoringApplication
from api.monitoring import NetworkMonitoring
from api.monitoring import WiktionaryIrcMonitoring


def setup_server():
    monitoring = MonitoringApplication()
    monitoring.add_component(WiktionaryIrcMonitoring)
    monitoring.add_component(NetworkMonitoring)
    monitoring.run()
    # monitoring_loop = loop.run_in_executor(executor, monitoring.run)


if __name__ == '__main__':
    setup_server()
