import { fireEvent, render, screen } from '@testing-library/react';
import '@testing-library/jest-dom';
import PlayerControls from './PlayerControls';

describe('PlayerControls', () => {
  it('provides playback and volume controls', () => {
    const onPlayPause = jest.fn();
    const onNext = jest.fn();
    const onPrevious = jest.fn();
    const onVolumeChange = jest.fn();
    render(<PlayerControls playing={false} volume={35} onPlayPause={onPlayPause} onNext={onNext} onPrevious={onPrevious} onVolumeChange={onVolumeChange} />);
    fireEvent.click(screen.getByRole('button', { name: 'Play' }));
    fireEvent.click(screen.getByRole('button', { name: 'Next' }));
    fireEvent.click(screen.getByRole('button', { name: 'Previous' }));
    expect(onPlayPause).toHaveBeenCalledTimes(1);
    expect(onNext).toHaveBeenCalledTimes(1);
    expect(onPrevious).toHaveBeenCalledTimes(1);
    expect(screen.getByRole('slider', { name: 'Volume' })).toHaveAttribute('aria-valuenow', '35');
    fireEvent.change(screen.getByRole('slider', { name: 'Volume' }), { target: { value: '36' } });
    expect(onVolumeChange).toHaveBeenCalledWith(36);
  });

  it('shows Pause while playing', () => {
    render(<PlayerControls playing volume={35} onPlayPause={jest.fn()} onNext={jest.fn()} onPrevious={jest.fn()} onVolumeChange={jest.fn()} />);
    expect(screen.getByRole('button', { name: 'Pause' })).toBeInTheDocument();
  });
});
