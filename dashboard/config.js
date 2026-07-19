// Fill these in with your Supabase project's URL and "anon public" key --
// both from Supabase dashboard: Settings -> API.
//
// This key is SAFE to commit and publish -- it's designed by Supabase to be
// embedded in public client-side code, unlike your database password. It
// only works within the boundaries of the Row Level Security policy you set
// up on your tables (see README section in this folder) -- with a read-only
// (or narrowly column-scoped) policy in place, this key can never be used
// beyond exactly what those policies allow.
//
// No Gemini key belongs here -- "Analyze this tender" works by setting a
// flag that a background job on the server picks up, so the AI key never
// needs to leave your machine at all.
const SUPABASE_CONFIG = {
  url: "https://behnqhrefhtmkjvikkox.supabase.co",
  anonKey: "sb_publishable_GuxJLVHMDPFQXTaFKa51Wg_SGtWltqQ",
};
