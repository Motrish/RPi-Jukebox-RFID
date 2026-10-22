import {
  Box,
  TextField,
  Button,
  Checkbox,
  FormControlLabel,
  Typography,
} from '@mui/material';
import React from 'react';

export default function SettingsPage({ initialValues, onSave }) {
  const [values, setValues] = React.useState(initialValues);
  const [errors, setErrors] = React.useState({});
  const [submitting, setSubmitting] = React.useState(false);
  const [submitError, setSubmitError] = React.useState('');
  const http = values.local_playback.http;
  const update = (key, value) => setValues(current => ({ ...current, local_playback: { ...current.local_playback, http: { ...current.local_playback.http, [key]: value } } }));
  const submit = async (event) => {
    event.preventDefault();
    if (submitting) return;
    const nextErrors = {};
    if (!Number.isInteger(Number(http.port)) || Number(http.port) < 1 || Number(http.port) > 65535) nextErrors.port = 'Port must be an integer from 1 to 65535';
    if (http.enabled && !http.bearer_token_path.trim()) nextErrors.bearer_token_path = 'Bearer token path is required when HTTP is enabled';
    setErrors(nextErrors);
    setSubmitError('');
    if (Object.keys(nextErrors).length) return;
    setSubmitting(true);
    try { await onSave({ ...values, local_playback: { ...values.local_playback, http: { ...http, port: Number(http.port) } } }); }
    catch (error) { setSubmitError(error?.message || 'Could not save settings'); }
    finally { setSubmitting(false); }
  };
  return (
    <Box sx={{ p: 3, maxWidth: 600 }}>
      <Typography variant="h5" gutterBottom>
        Playback Settings
      </Typography>
      <Typography variant="body2" color="text.secondary" paragraph>
        Konfigurationsentwurf, ändert keinen Daemon ohne angeschlossenen Speicherdienst.
      </Typography>

      <form onSubmit={submit}>
            <Box sx={{ mb: 2 }}>
              <FormControlLabel
                control={
                  <Checkbox checked={http.enabled} onChange={(event) => update('enabled', event.target.checked)} />
                }
                label="Enable Local Playback HTTP"
              />
            </Box>

            <TextField
              label="Bearer Token Path"
              value={http.bearer_token_path}
              onChange={event => update('bearer_token_path', event.target.value)}
              fullWidth
              margin="normal"
              disabled={!http.enabled}
              error={Boolean(errors.bearer_token_path)}
              helperText={errors.bearer_token_path || 'Path to the HTTP bearer token file'}
            />
            <TextField
              type="number"
              value={http.port}
              onChange={event => update('port', event.target.value)}
              label="Port"
              fullWidth
              margin="normal"
              inputProps={{ min: 1, max: 65535 }}
              error={Boolean(errors.port)}
              helperText={errors.port || ''}
            />
            {submitError && <Typography role="alert" color="error">{submitError}</Typography>}

            <Box sx={{ mt: 2 }}>
              <Button
                type="submit"
                variant="contained"
                color="primary"
                disabled={submitting}
              >
                {submitting ? 'Saving...' : 'Save Settings'}
              </Button>
            </Box>
      </form>
    </Box>
  );
}
