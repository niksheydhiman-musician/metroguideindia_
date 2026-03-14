/**
 * routeMetadata.js — ROUTE_METADATA data module
 *
 * Maps canonical station-pair keys to route data:
 *   distance_km        (number)
 *   travel_time_mins   (number)
 *   route_type         'RRTS' | 'Metro' | 'Interchange'
 *
 * Keys are direction-agnostic: get() tries both A→B and B→A.
 * Station IDs match the canonical IDs used throughout the app
 * (e.g. anand_vihar, meerut_south_rrts, modipuram_rrts,
 *  brahampuri_meerut_metro, etc.).
 */
const RouteMetadata = (() => {

  const ROUTE_METADATA = {
    // ── Namo Bharat RRTS routes ───────────────────────────────────────────────
    'sarai_kale_khan__modipuram_rrts':         { distance_km: 82.15, travel_time_mins: 58, route_type: 'RRTS' },
    'anand_vihar__meerut_south_rrts':          { distance_km: 44.3,  travel_time_mins: 38, route_type: 'RRTS' },
    'ghaziabad__shatabdi_nagar_rrts':          { distance_km: 39.6,  travel_time_mins: 28, route_type: 'RRTS' },
    'anand_vihar__ghaziabad':                  { distance_km: 10.8,  travel_time_mins: 10, route_type: 'RRTS' },
    'new_ashok_nagar__modipuram_rrts':         { distance_km: 70.5,  travel_time_mins: 50, route_type: 'RRTS' },
    'sahibabad__modipuram_rrts':               { distance_km: 64.1,  travel_time_mins: 46, route_type: 'RRTS' },
    'meerut_south_rrts__modipuram_rrts':       { distance_km: 18.9,  travel_time_mins: 22, route_type: 'RRTS' },
    'sarai_kale_khan__anand_vihar':            { distance_km: 9.5,   travel_time_mins: 8,  route_type: 'RRTS' },
    'ghaziabad__murad_nagar':                  { distance_km: 14.5,  travel_time_mins: 12, route_type: 'RRTS' },
    'modi_nagar_north__meerut_south_rrts':     { distance_km: 11.2,  travel_time_mins: 11, route_type: 'RRTS' },
    'sarai_kale_khan__ghaziabad':              { distance_km: 22.7,  travel_time_mins: 20, route_type: 'RRTS' },
    'new_ashok_nagar__meerut_south_rrts':      { distance_km: 55.1,  travel_time_mins: 40, route_type: 'RRTS' },
    'sahibabad__meerut_south_rrts':            { distance_km: 44.3,  travel_time_mins: 38, route_type: 'RRTS' },
    'anand_vihar__modipuram_rrts':             { distance_km: 73.4,  travel_time_mins: 52, route_type: 'RRTS' },
    'ghaziabad__modipuram_rrts':               { distance_km: 62.3,  travel_time_mins: 44, route_type: 'RRTS' },
    'modi_nagar_north__modipuram_rrts':        { distance_km: 30.1,  travel_time_mins: 25, route_type: 'RRTS' },
    'duhai__meerut_south_rrts':               { distance_km: 35.5,  travel_time_mins: 30, route_type: 'RRTS' },

    // ── Meerut Metro routes ────────────────────────────────────────────────────
    'meerut_south_meerut_metro__modipuram_meerut_metro': { distance_km: 18.9, travel_time_mins: 28, route_type: 'Metro' },
    'meerut_south_meerut_metro__begumpul_meerut_metro':  { distance_km: 9.3,  travel_time_mins: 16, route_type: 'Metro' },
    'shatabdi_nagar_meerut_metro__meerut_north_meerut_metro': { distance_km: 6.2, travel_time_mins: 13, route_type: 'Metro' },

    // ── RRTS + Metro Interchange routes ──────────────────────────────────────
    'anand_vihar__brahampuri_meerut_metro':        { distance_km: 49.5, travel_time_mins: 48, route_type: 'Interchange' },
    'ghaziabad__meerut_north_meerut_metro':        { distance_km: 52.1, travel_time_mins: 50, route_type: 'Interchange' },
    'new_ashok_nagar__bhaisali_bus_adda_meerut_metro': { distance_km: 72.4, travel_time_mins: 58, route_type: 'Interchange' },
    'sarai_kale_khan__meerut_central_meerut_metro': { distance_km: 79.8, travel_time_mins: 62, route_type: 'Interchange' },
  };

  /**
   * Direction-agnostic lookup — returns the metadata entry for
   * either (stationA → stationB) or (stationB → stationA).
   * Returns null if no entry exists.
   */
  function get(stationA, stationB) {
    return ROUTE_METADATA[`${stationA}__${stationB}`]
        || ROUTE_METADATA[`${stationB}__${stationA}`]
        || null;
  }

  return { ROUTE_METADATA, get };
})();
