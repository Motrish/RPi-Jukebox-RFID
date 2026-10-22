import { fireEvent, render, screen } from '@testing-library/react';
import { jest } from '@jest/globals';
import LibraryBrowser from './LibraryBrowser';

test('filters by title and artist, shows cover art and supports selecting a track', () => {
    const onSelect = jest.fn();
    render(<LibraryBrowser items={[{ id: '1', title: 'Moonlight', artist: 'Ada', coverUrl: '/moon.jpg' }, { id: '2', title: 'Sunrise', artist: 'Bo' }]} onSelect={onSelect} />);
    expect(screen.getByRole('img', { name: 'Moonlight cover' })).toHaveAttribute('src', '/moon.jpg');
    fireEvent.change(screen.getByRole('searchbox', { name: 'Search library' }), { target: { value: 'bo' } });
    expect(screen.getByText('Sunrise')).toBeInTheDocument();
    expect(screen.queryByText('Moonlight')).not.toBeInTheDocument();
    fireEvent.click(screen.getByText('Sunrise'));
    expect(onSelect).toHaveBeenCalledWith({ id: '2', title: 'Sunrise', artist: 'Bo' });
});
