import { useState } from "react";

/**
 * Sync zone tour + swatch options from API payloads.
 *
 * Clears tour chrome when ``zone_tour`` is missing or ``active: false``. Swatch
 * options live on each assistant chat message, not a separate bottom panel.
 * Exposes ``syncZoneTourFromApi`` for
 * ``applyApiData`` after each chat response.
 */
export function useZoneTourSync() {
  const [zoneTour, setZoneTour] = useState(null);

  function syncZoneTourFromApi(data) {
    if (data?.zone_tour?.active) {
      setZoneTour(data.zone_tour);
    } else {
      setZoneTour(null);
    }
  }

  function clearZoneTour() {
    setZoneTour(null);
  }

  return {
    zoneTour,
    syncZoneTourFromApi,
    clearZoneTour,
  };
}
