// ============================================
// MOCK DATA — OpportUnity Hub
// In production, this is replaced by Firebase calls
// ============================================

const MOCK_OPPORTUNITIES = [];

function daysFromNow(n) {
  const d = new Date();
  d.setDate(d.getDate() + n);
  return d.toISOString().split("T")[0];
}

function getDaysLeft(dateStr) {
  if (!dateStr || dateStr === "N/A" || dateStr === "-") return Infinity;
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const target = new Date(dateStr);
  if (isNaN(target.getTime())) return Infinity;
  const diff = Math.round((target - today) / (1000 * 60 * 60 * 24));
  return diff;
}

function formatDeadline(dateStr) {
  const d = new Date(dateStr);
  return d.toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" });
}

function getUrgencyBadge(daysLeft) {
  if (daysLeft < 0) return { label: "Expired", class: "badge-critical", emoji: "✗" };
  if (daysLeft === 0) return { label: "Today!", class: "badge-critical", emoji: "🔥" };
  if (daysLeft <= 2) return { label: `${daysLeft}d left`, class: "badge-critical", emoji: "🔥" };
  if (daysLeft <= 7) return { label: `${daysLeft}d left`, class: "badge-urgent", emoji: "⚡" };
  if (daysLeft <= 14) return { label: `${daysLeft}d left`, class: "badge internship", emoji: "📅" };
  return { label: `${daysLeft}d left`, class: "", emoji: "🗓️" };
}

const SOURCE_ICONS = {
  internshala: "🎓",
  devpost: "💻",
  linkedin: "💼",
  unstop: "🚀",
  remotive: "🌍",
  gmail: "📧",
  email: "📧",
};

const SOURCE_LABELS = {
  internshala: "Internshala",
  devpost: "Devpost",
  linkedin: "LinkedIn",
  unstop: "Unstop",
  remotive: "Remotive",
  gmail: "Gmail",
  email: "Email",
}; 