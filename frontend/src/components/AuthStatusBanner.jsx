export default function AuthStatusBanner({ authInitError }) {
  if (!authInitError) return null;
  return (
    <div className="error-banner" role="alert">
      {authInitError}
    </div>
  );
}
