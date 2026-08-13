export async function loadProfile() {
  const response = await fetch('/api/profile');
  return response.json();
}

export async function billingLabel() {
  const profile = await loadProfile();
  return `Credits remaining: ${profile.credits}`;
}
