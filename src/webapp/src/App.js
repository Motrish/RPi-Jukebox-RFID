import React, { Suspense } from 'react';

import Grid from '@mui/material/Grid';

const DesignPreview = React.lazy(() => import('./components/DesignPreview'));
const LegacyPubSubProvider = React.lazy(() => import('./context/pubsub'));
const LegacyPlayerProvider = React.lazy(() => import('./context/player'));
const LegacyAppSettingsProvider = React.lazy(() => import('./context/appsettings'));
const LegacyRouter = React.lazy(() => import('./router'));

function isDesignPreviewBoot() {
  if (typeof window === 'undefined') return false;
  const path = window.location.hash.slice(1).split(/[?#]/, 1)[0];
  return path === '/design-preview' || path.startsWith('/design-preview/');
}

function LegacyApp() {
  return (
    <LegacyPubSubProvider>
      <LegacyPlayerProvider>
        <LegacyAppSettingsProvider>
          <Grid
            alignItems="center"
            container
            direction="row"
            id="routes"
            justifyContent="center"
          >
            <LegacyRouter />
          </Grid>
        </LegacyAppSettingsProvider>
      </LegacyPlayerProvider>
    </LegacyPubSubProvider>
  );
}

export default function App() {
  const [previewBoot] = React.useState(isDesignPreviewBoot);

  return (
    <Suspense fallback="Loading ...">
      {previewBoot ? <DesignPreview /> : <LegacyApp />}
    </Suspense>
  );
}
