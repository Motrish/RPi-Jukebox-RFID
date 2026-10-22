import { IconButton, Slider } from '@mui/material';
import { PlayArrow, Pause, SkipNext, SkipPrevious } from '@mui/icons-material';
import React from 'react';

export default function PlayerControls({
  playing,
  volume,
  onPlayPause,
  onNext,
  onPrevious,
  onVolumeChange,
}) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 16, padding: 16 }}>
      <IconButton
        onClick={onPrevious}
        aria-label="Previous"
        size="large"
      >
        <SkipPrevious />
      </IconButton>

      <IconButton
        onClick={onPlayPause}
        aria-label={playing ? 'Pause' : 'Play'}
        size="large"
      >
        {playing ? <Pause /> : <PlayArrow />}
      </IconButton>

      <IconButton
        onClick={onNext}
        aria-label="Next"
        size="large"
      >
        <SkipNext />
      </IconButton>

      <div style={{ flex: 1, maxWidth: 200, marginLeft: 16 }}>
        <label htmlFor="volume-slider" style={{ display: 'none' }}>
          Volume
        </label>
        <Slider
          id="volume-slider"
          value={volume}
          onChange={(_event, value) => onVolumeChange(value)}
          min={0}
          max={100}
          step={1}
          aria-label="Volume"
          valueLabelDisplay="auto"
        />
      </div>
    </div>
  );
}
