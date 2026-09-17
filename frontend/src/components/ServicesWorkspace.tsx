import { useEffect, useEffectEvent, useRef, useState } from "react";

import { changeManagedService, getManagedServices } from "../api";
import { useI18n } from "../i18n";
import { servicesMessages } from "../messages/services";
import type { ManagedService, SupervisorHostStatus } from "../types";

interface ServicesWorkspaceProps {
  onMessage: (message: string, tone?: "success" | "error") => void;
}

type ServiceFilter = "all" | "running" | "stopped" | "problems";

function formatUptime(seconds: number): string {
  if (seconds < 60) return `${seconds}s`;
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m`;
  if (seconds < 86400) return `${Math.floor(seconds / 3600)}h`;
  return `${Math.floor(seconds / 86400)}d`;
}

export function ServicesWorkspace({ onMessage }: ServicesWorkspaceProps) {
  const { locale, t } = useI18n();
  const [hosts, setHosts] = useState<SupervisorHostStatus[]>([]);
  const [loading, setLoading] = useState(true);
  const [pending, setPending] = useState("");
  const [filter, setFilter] = useState<ServiceFilter>("all");
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);
  const [pollingError, setPollingError] = useState("");
  const requestVersion = useRef(0);
  const reportPollingError = useEffectEvent((caught: unknown) => {
    const message = caught instanceof Error ? caught.message : t("Tsy azo ny satan'ny tolotra.", "Unable to load service status.");
    setPollingError(message);
    onMessage(message, "error");
  });

  async function refresh(signal?: AbortSignal) {
    const version = ++requestVersion.current;
    try {
      const response = await getManagedServices(signal);
      if (version !== requestVersion.current) return;
      setHosts(response.hosts);
      setLastUpdated(new Date());
      setPollingError("");
    } catch (caught) {
      if (signal?.aborted) return;
      if (version !== requestVersion.current) return;
      const message = caught instanceof Error ? caught.message : t("Tsy azo ny satan'ny tolotra.", "Unable to load service status.");
      setPollingError(message);
      onMessage(message, "error");
    } finally {
      if (!signal?.aborted && version === requestVersion.current) setLoading(false);
    }
  }

  useEffect(() => {
    const controller = new AbortController();
    let timeout: number | undefined;
    async function poll() {
      const version = ++requestVersion.current;
      try {
        const response = await getManagedServices(controller.signal);
        if (version !== requestVersion.current) return;
        setHosts(response.hosts);
        setLastUpdated(new Date());
        setPollingError("");
      } catch (caught) {
        if (!controller.signal.aborted && version === requestVersion.current) reportPollingError(caught);
      } finally {
        if (!controller.signal.aborted) {
          if (version === requestVersion.current) setLoading(false);
          timeout = window.setTimeout(poll, 30_000);
        }
      }
    }
    void poll();
    return () => {
      controller.abort();
      window.clearTimeout(timeout);
    };
  }, []);

  function replaceService(updated: ManagedService) {
    setHosts((current) => current.map((host) => host.id === updated.host_id
      ? { ...host, services: host.services.map((service) => service.id === updated.id ? updated : service) }
      : host));
  }

  async function changeService(host: SupervisorHostStatus, service: ManagedService) {
    const action = service.running ? "stop" : "start";
    const serviceLabel = service.id.replaceAll("\\", "\\\\").replaceAll('"', '\\"');
    const hostLabel = host.label.replaceAll("\\", "\\\\").replaceAll('"', '\\"');
    const prompt = action === "stop"
      ? t(`Hajanona ve ny "${serviceLabel}" ao amin'ny "${hostLabel}"?`, `Stop "${serviceLabel}" on "${hostLabel}"?`)
      : t(`Halefa ve ny "${serviceLabel}" ao amin'ny "${hostLabel}"?`, `Start "${serviceLabel}" on "${hostLabel}"?`);
    if (!window.confirm(prompt)) return;

    const key = `${host.id}/${service.id}`;
    setPending(key);
    try {
      const updated = await changeManagedService(host.id, service.id, action);
      replaceService(updated);
      onMessage(action === "stop" ? t("Najanona ny tolotra.", "Service stopped.") : t("Nalefa ny tolotra.", "Service started."));
    } catch (caught) {
      onMessage(caught instanceof Error ? caught.message : t("Tsy voaova ny satan'ny tolotra.", "Unable to change service state."), "error");
    } finally {
      setPending("");
    }
  }

  const services = hosts.flatMap((host) => host.services);
  const unavailableHosts = hosts.filter((host) => !host.available).length;
  const runningServices = services.filter((service) => service.running).length;
  const problemServices = services.filter((service) => service.state === "unavailable" || (!["running", "stopped", "exited"].includes(service.state))).length;
  const stoppedServices = services.filter((service) => !service.running && ["stopped", "exited"].includes(service.state)).length;
  const visibleHosts = hosts.flatMap((host) => {
    if (filter === "problems" && !host.available) return [host];
    const filteredServices = host.services.filter((service) => filter === "all"
      || (filter === "running" && service.running)
      || (filter === "stopped" && !service.running && service.state !== "unavailable")
      || (filter === "problems" && (service.state === "unavailable" || !["running", "stopped", "exited"].includes(service.state))));
    return filteredServices.length ? [{ ...host, services: filteredServices }] : [];
  });
  const filters: Array<{ id: ServiceFilter; label: string; count: number }> = [
    { id: "all", label: t("Rehetra", "All"), count: services.length },
    { id: "running", label: t("Mandeha", "Running"), count: runningServices },
    { id: "stopped", label: t("Mijanona", "Stopped"), count: stoppedServices },
    { id: "problems", label: t("Olana", "Problems"), count: problemServices + unavailableHosts },
  ];

  return (
    <div className="services-workspace">
      <section className="services-intro panel">
        <div><p className="eyebrow">Supervisor / allowlisted control</p><h2>{t("Fanaraha-maso ny tolotra", "Service control")}</h2><p>{t("Jereo ary alefaso na ajanony ireo tolotra voafantina amin'ny mpizara lavitra. Ny mpizara ihany no mamaritra ny hosts sy programs azo fehezina.", "Inspect, start, or stop selected services on remote hosts. The server exclusively defines which hosts and programs can be controlled.")}</p></div>
        <div className="services-refresh"><small>{lastUpdated ? t(`Nohavaozina ${lastUpdated.toLocaleTimeString(locale)}`, `Updated ${lastUpdated.toLocaleTimeString(locale)}`) : t("Tsy mbola nohavaozina", "Not updated yet")}</small><button className="button button--ghost" disabled={loading || Boolean(pending)} type="button" onClick={() => { setLoading(true); void refresh(); }}>{loading ? t("Manavao...", "Refreshing...") : t("Hanavao sata", "Refresh status")}</button></div>
      </section>

      {pollingError && <div className="notice notice--error services-polling-error" role="alert"><span><strong>{t(...servicesMessages.latestStatusUnavailable)}</strong> {pollingError} {t(...servicesMessages.retryingAutomatically)}</span><button className="button button--ghost" disabled={loading} type="button" onClick={() => { setLoading(true); void refresh(); }}>{t(...servicesMessages.retryNow)}</button></div>}

      {loading && !hosts.length ? <div className="services-state panel"><span className="spinner" />{t("Maka ny satan'ny tolotra...", "Loading service status...")}</div> : (
        <>
          <section className="services-overview" aria-label={t("Topimaso momba ny tolotra", "Service overview")}>
            <article><span>{t("Hosts mifandray", "Connected hosts")}</span><strong>{hosts.length - unavailableHosts}<small> / {hosts.length}</small></strong></article>
            <article><span>{t("Tolotra mandeha", "Running services")}</span><strong>{runningServices}<small> / {services.length}</small></strong></article>
            <article className={stoppedServices ? "services-overview__warning" : ""}><span>{t("Tolotra mijanona", "Stopped services")}</span><strong>{stoppedServices}</strong></article>
            <article className={problemServices + unavailableHosts ? "services-overview__danger" : ""}><span>{t("Olana hita", "Detected problems")}</span><strong>{problemServices + unavailableHosts}</strong></article>
          </section>
          <nav className="services-filters" aria-label={t("Sivana satan'ny tolotra", "Service status filters")}>
            {filters.map((item) => <button className={filter === item.id ? "services-filter services-filter--active" : "services-filter"} type="button" aria-label={`${item.label}: ${item.count}`} aria-pressed={filter === item.id} key={item.id} onClick={() => setFilter(item.id)}>{item.label}<span>{item.count}</span></button>)}
          </nav>
          <div className="services-hosts">
          {visibleHosts.map((host) => (
            <section className="services-host panel" key={host.id}>
              <header>
                <div><p className="eyebrow">{host.id}</p><h3>{host.label}</h3></div>
                <span className={host.available ? "host-availability host-availability--online" : "host-availability host-availability--offline"}>{host.available ? t("Mifandray", "Connected") : t("Tsy mifandray", "Unavailable")}</span>
              </header>
              {host.services.length > 0 ? <div className="managed-service-list">
                {host.services.map((service) => {
                  const key = `${host.id}/${service.id}`;
                  return <article className="managed-service" key={service.id}>
                    <span className={`managed-service__state managed-service__state--${service.running ? "running" : "stopped"}`} />
                    <div><strong>{service.id}</strong><small>{service.description || service.state}</small></div>
                    <dl><div><dt>PID</dt><dd>{service.pid || "-"}</dd></div><div><dt>{t("Fotoana", "Uptime")}</dt><dd>{service.running ? formatUptime(service.uptime_seconds) : "-"}</dd></div></dl>
                    <button className={service.running ? "button button--danger" : "button button--primary"} disabled={pending === key || service.state === "unavailable"} type="button" onClick={() => void changeService(host, service)}>{pending === key ? t("Miandry...", "Working...") : service.running ? t("Hajanona", "Stop") : t("Halefa", "Start")}</button>
                  </article>;
                })}
              </div> : <div className="empty-inline">{host.available ? t("Tsy misy tolotra azo fehezina.", "No controllable services are configured.") : t("Tsy namaly ny Supervisor lavitra.", "The remote Supervisor did not respond.")}</div>}
            </section>
          ))}
          {!hosts.length && <section className="services-state panel">{t("Tsy mbola misy host Supervisor voakirakira.", "No Supervisor hosts are configured yet.")}</section>}
          {hosts.length > 0 && !visibleHosts.length && <section className="services-state panel">{t("Tsy misy tolotra mifanaraka amin'ity sivana ity.", "No services match this filter.")}</section>}
          </div>
        </>
      )}
    </div>
  );
}
