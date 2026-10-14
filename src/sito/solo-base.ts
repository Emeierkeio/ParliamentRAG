/*
 * Numeri che il sito prende solo da dati-base.json, mai dal backend.
 *
 * government_without_seat: /api/data/stats conta le cariche di Governo finite
 * dal 13/10/2022 in poi, quindi anche il Governo Draghi (in carica fino al
 * 22/10/2022): restituisce 48. I membri del Governo Meloni senza seggio alla
 * Camera o al Senato nella XIX legislatura sono 23 (dati.camera.it e
 * dati.senato.it, verificato il 14/10/2026). Togliere da qui quando il backend
 * conta solo il Governo della legislatura.
 */
export const SOLO_BASE: string[] = ["government_without_seat"];
