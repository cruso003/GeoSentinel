import { useSiteStore } from '@/store/siteStore';
import { useUIStore } from '@/store/uiStore';

interface Props {
  className?: string;
}

// Dropdown populated from /me/sites (or MOCK_SITES in mock mode). A
// single-site user sees a read-only label; a multi-site user gets a real
// picker that updates uiStore.activeSiteId — useDataEngine re-hydrates
// when that changes.
export function SiteSwitcher({ className }: Props) {
  const sites = useSiteStore((s) => s.sites);
  const loaded = useSiteStore((s) => s.loaded);
  const loading = useSiteStore((s) => s.loading);
  const error = useSiteStore((s) => s.error);
  const activeSiteId = useUIStore((s) => s.activeSiteId);
  const setSiteId = useUIStore((s) => s.setActiveSiteId);

  if (!loaded && loading) {
    return (
      <div className={className}>
        <label className="text-[10px] uppercase tracking-wider text-slate-500">Site</label>
        <div className="gs-input mt-1 text-xs opacity-50">Loading sites…</div>
      </div>
    );
  }

  if (sites.length === 0) {
    return (
      <div className={className}>
        <label className="text-[10px] uppercase tracking-wider text-slate-500">Site</label>
        <div className="gs-input mt-1 text-xs opacity-60">No sites assigned</div>
        {error && (
          <p className="mt-1 text-[10px] text-red-400" role="alert">
            {error}
          </p>
        )}
      </div>
    );
  }

  return (
    <div className={className}>
      <label className="text-[10px] uppercase tracking-wider text-slate-500" htmlFor="gs-site-switcher">
        Site
      </label>
      <select
        id="gs-site-switcher"
        value={activeSiteId}
        onChange={(e) => setSiteId(e.target.value)}
        className="gs-input mt-1 text-xs"
        disabled={sites.length === 1}
        aria-label="Active site"
      >
        {sites.map((s) => (
          <option key={s.id} value={s.id}>
            {s.name}
          </option>
        ))}
      </select>
    </div>
  );
}
