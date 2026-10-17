export const DEMO_BATTERY_PERCENT = 82;

export const TRACKS = Object.freeze([
  Object.freeze({
    id: 'morgens-im-garten',
    title: 'Morgens im Garten',
    artist: 'Mira & die Wolken',
    source: 'Eigene Musik',
    cover: 'cover-sun',
    search: 'morgens im garten mira die wolken eigene musik',
  }),
  Object.freeze({
    id: 'leise-wellen',
    title: 'Leise Wellen',
    artist: 'Nordlicht',
    source: 'Spotify',
    cover: 'cover-wave',
    search: 'leise wellen nordlicht spotify',
  }),
  Object.freeze({
    id: 'kleiner-komet',
    title: 'Kleiner Komet',
    artist: 'Die Sternfahrer',
    source: 'Eigene Musik',
    cover: 'cover-comet',
    search: 'kleiner komet sternfahrer eigene musik',
  }),
  Object.freeze({
    id: 'komm-wir-gehen',
    title: 'Komm, wir gehen',
    artist: 'Lotte im Park',
    source: 'Spotify',
    cover: 'cover-park',
    search: 'komm wir gehen lotte im park spotify',
  }),
  Object.freeze({
    id: 'tanz-im-flur',
    title: 'Tanz im Flur',
    artist: 'Papierflieger',
    source: 'Eigene Musik',
    cover: 'cover-dance',
    search: 'tanz im flur papierflieger eigene musik',
  }),
  Object.freeze({
    id: 'wolken-zaehlen',
    title: 'Wolken zählen',
    artist: 'Juno Blau',
    source: 'Spotify',
    cover: 'cover-cloud',
    search: 'wolken zählen juno blau spotify',
  }),
  Object.freeze({
    id: 'normaler-tag',
    title: 'Ein ganz normaler Tag',
    artist: 'Mira & die Wolken',
    source: 'Eigene Musik',
    cover: 'cover-sun',
    search: 'ein ganz normaler tag mira die wolken eigene musik',
  }),
]);

export const RECENT_TRACK_IDS = Object.freeze([
  'normaler-tag',
  'leise-wellen',
  'kleiner-komet',
]);

export const INITIAL_TRACK_ID = 'morgens-im-garten';

export function getTrack(trackId) {
  return TRACKS.find((track) => track.id === trackId) || TRACKS[0];
}

export function getRelativeTrack(trackId, offset) {
  const currentIndex = Math.max(0, TRACKS.findIndex((track) => track.id === trackId));
  const nextIndex = (currentIndex + offset + TRACKS.length) % TRACKS.length;
  return TRACKS[nextIndex];
}

export function getUpcomingTracks(trackId, count = 2) {
  return Array.from({ length: count }, (_, index) => getRelativeTrack(trackId, index + 1));
}

export function filterTracks(query, source) {
  const normalizedQuery = query.trim().toLocaleLowerCase('de');
  return TRACKS.filter((track) => {
    const matchesSource = !source || track.source === source;
    const matchesQuery = !normalizedQuery || track.search.includes(normalizedQuery);
    return matchesSource && matchesQuery;
  });
}
