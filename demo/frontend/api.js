export async function loadProfile() {
  const response = await fetch('/api/profile');
  return response.json();
}

export async function billingLabel() {
  const response = await loadProfile();
  return `Credits remaining: ${response.credits}`;
}
