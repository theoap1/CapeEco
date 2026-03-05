import html2canvas from 'html2canvas';

/**
 * Capture the Leaflet map container as a data-URL PNG.
 * Works because Leaflet renders tiles as <img> (CORS-enabled) and GeoJSON as SVG.
 */
export async function captureMapImage(mapInstance) {
  const el = mapInstance?._container;
  if (!el) return null;

  const canvas = await html2canvas(el, {
    useCORS: true,
    scale: 2,
    logging: false,
    backgroundColor: null,
  });
  return canvas.toDataURL('image/png');
}
