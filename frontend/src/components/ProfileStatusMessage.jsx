export default function ProfileStatusMessage({ profileStatus }) {
  if (!profileStatus) return null;
  return <p>{profileStatus}</p>;
}
