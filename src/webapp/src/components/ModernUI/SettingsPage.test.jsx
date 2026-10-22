import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { describe, expect, it, jest } from '@jest/globals';
import SettingsPage from './SettingsPage';

describe('SettingsPage', () => {
  it('submits opted-in HTTP configuration', async () => {
    const onSave = jest.fn();
    render(<SettingsPage initialValues={{ local_playback: { http: { enabled: false, bearer_token_path: '', port: 8090 } } }} onSave={onSave} />);
    fireEvent.click(screen.getByRole('checkbox', { name: /enable local playback http/i }));
    fireEvent.change(screen.getByLabelText(/bearer token path/i), { target: { value: '/run/token' } });
    fireEvent.click(screen.getByRole('button', { name: /save settings/i }));
    await waitFor(() => expect(onSave).toHaveBeenCalledWith({ local_playback: { http: { enabled: true, bearer_token_path: '/run/token', port: 8090 } } }));
  });

  it('requires an integer port from 1 through 65535', async () => {
    const onSave = jest.fn();
    render(<SettingsPage initialValues={{ local_playback: { http: { enabled: false, bearer_token_path: '', port: 8090 } } }} onSave={onSave} />);
    fireEvent.change(screen.getByLabelText(/port/i), { target: { value: '65536' } });
    fireEvent.click(screen.getByRole('button', { name: /save settings/i }));
    expect(await screen.findByText(/integer from 1 to 65535/i)).toBeInTheDocument();
    expect(onSave).not.toHaveBeenCalled();
  });

  it('shows async save failures and prevents a second submit while saving', async () => {
    let rejectSave;
    const onSave = jest.fn(() => new Promise((_, reject) => { rejectSave = reject; }));
    render(<SettingsPage initialValues={{ local_playback: { http: { enabled: false, bearer_token_path: '', port: 8090 } } }} onSave={onSave} />);
    const button = screen.getByRole('button', { name: /save settings/i });
    fireEvent.click(button);
    expect(await screen.findByRole('button', { name: /saving/i })).toBeDisabled();
    fireEvent.click(screen.getByRole('button', { name: /saving/i }));
    expect(onSave).toHaveBeenCalledTimes(1);
    rejectSave(new Error('Storage unavailable'));
    expect(await screen.findByRole('alert')).toHaveTextContent('Storage unavailable');
  });
});
