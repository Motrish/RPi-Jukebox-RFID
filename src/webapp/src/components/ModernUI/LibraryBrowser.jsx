import { TextField, List, ListItem, ListItemAvatar, ListItemText } from '@mui/material';
import React, { useMemo } from 'react';

export default function LibraryBrowser({ items, onSelect }) {
  const [search, setSearch] = React.useState('');

  const filteredItems = useMemo(
    () => items.filter((track) =>
      track.title.toLowerCase().includes(search.toLowerCase()) ||
      track.artist.toLowerCase().includes(search.toLowerCase())
    ),
    [items, search]
  );

  return (
    <div style={{ padding: 16, height: '100%', display: 'flex', flexDirection: 'column' }}>
      <TextField
        id="library-search"
        label="Search library"
        type="search"
        value={search}
        onChange={(e) => setSearch(e.target.value)}
        placeholder="Search tracks..."
        fullWidth
        style={{ marginBottom: 16 }}
      />
      <div style={{ flex: 1, overflow: 'auto' }}>
        {filteredItems.length === 0 ? (
          <div role="status">No tracks found</div>
        ) : (
        <List
          aria-label="Track library"
        >
          {filteredItems.map((track) => <ListItem key={track.id} button onClick={() => onSelect(track)}>
            {track.coverUrl && <ListItemAvatar><img src={track.coverUrl} alt={`${track.title} cover`} style={{ width: 40, height: 40, borderRadius: 4 }} /></ListItemAvatar>}
            <ListItemText primary={track.title} secondary={track.artist} />
          </ListItem>)}
        </List>
        )}
      </div>
    </div>
  );
}
