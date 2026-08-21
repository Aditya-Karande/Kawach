// ---------------------------------------------------------------------
// CUSTOM BUILD-UP MODE (new)
// ---------------------------------------------------------------------
// Lets you pick ONE signal type (chat / search / website visits) and a
// target level (safe / tier 2 / tier 3), and plays a clean, single-type
// sequence where the score climbs step by step as safety decreases,
// stopping right at the level you asked for.
//
// Every escalation phrase below is copied verbatim from the backend's
// own deterministic keyword lists (models/keyword_rules.py) -- NOT from
// the ML classifier -- so every step's weight is guaranteed and
// reproducible, not a probabilistic guess. The point value shown next
// to each step is the same core/scoring.py weight the real backend will
// assign; nothing here is invented for the demo.
//
// Thresholds (core/scoring.py): tier 1 = score 1-2, tier 2 = score 3-5,
// tier 3 = score 6+.

const SIGNAL_TYPE_META = {
  chat_text: { label: 'Chat messages', speakerFor: () => 'stranger' },
  search_query: { label: 'Search queries', speakerFor: () => 'child' },
  url_visit: { label: 'Website visits', speakerFor: () => 'child' },
  file_upload: { label: 'File upload (not scored yet)', disabled: true }
};

// 2 ordinary, benign steps per signal type -- used for the "Safe" level
// and as the opening of every ladder so the score visibly starts at 0.
const SAFE_STEPS = {
  chat_text: [
    { content: "hii!! saw ur comment on that game clip, you're really good at this", weight: 0, note: 'Ordinary friendly chat -- scores 0.' },
    { content: 'yeah! see you at 6, I finished my part already', weight: 0, note: 'A classmate confirming plans -- scores 0.' }
  ],
  search_query: [
    { content: 'fractions homework help grade 6', weight: 0, note: 'Ordinary homework search -- scores 0.' },
    { content: 'best pizza toppings ranked', weight: 0, note: 'Ordinary curiosity search -- scores 0.' }
  ],
  url_visit: [
    { content: 'https://www.khanacademy.org/math/pre-algebra', weight: 0, note: 'Ordinary educational site -- scores 0.' },
    { content: 'https://www.nationalgeographic.com/animals', weight: 0, note: 'Ordinary browsing -- scores 0.' }
  ]
};

// Escalating steps, in order, each carrying its real backend weight.
// The builder below slices this list to land exactly in the tier the
// user asked to showcase.
const ESCALATION_LADDERS = {
  chat_text: [
    { content: "let's delete our messages after this, ok?", weight: 2, label: 'concealment', note: 'Matches keyword "delete our messages" -- concealment, weight +2.' },
    { content: "you're so mature for your age, most people your age wouldn't get it", weight: 3, label: 'grooming', note: 'Matches keyword "you\'re so mature" -- grooming-pattern flattery, weight +3.' },
    { content: "what's your real name and where do you go to school", weight: 3, label: 'personal_info_request', note: 'Matches keyword "what\'s your real name" -- personal info request, weight +3.' },
    { content: "let's talk on a different app instead, and don't tell your parents", weight: 3, label: 'platform_switch_request', note: 'Matches keyword "different app" -- platform-switch + secrecy, weight +3.' }
  ],
  search_query: [
    { content: 'free robux generator no human verification', weight: 1, label: 'scam', note: 'Scam-adjacent phrasing -- weight +1.' },
    { content: 'how to hide browser history from parents', weight: 2, label: 'concealment', note: 'Matches keyword "hide browser history" -- concealment, weight +2.' },
    { content: 'quick way to clear your history without anyone noticing', weight: 2, label: 'concealment', note: 'Matches keyword "clear your history" -- concealment, weight +2.' },
    { content: 'best way to hide my browser history fast', weight: 2, label: 'concealment', note: 'Matches keyword "hide my browser history" -- concealment, weight +2.' }
  ],
  url_visit: [
    { content: 'https://claim-your-prize-now.xyz/robux', weight: 2, label: 'unconfirmed', note: 'Matches scam-URL pattern "claim-your-prize" -- weight +2.' },
    { content: 'https://verify-your-account-freevbucks.top/', weight: 2, label: 'unconfirmed', note: 'Matches scam-URL pattern "verify-your-account" -- weight +2.' },
    { content: 'https://you-have-won-a-prize.club/claim', weight: 2, label: 'unconfirmed', note: 'Matches scam-URL pattern "you-have-won" -- weight +2.' }
  ]
};

const TIER_LEVEL_META = {
  safe: { label: 'Safe (no threat)', minScore: 0, maxScore: 0 },
  tier2: { label: 'Tier 2 -- gentle nudge to the child', minScore: 3, maxScore: 5 },
  tier3: { label: 'Tier 3 -- parent alerted', minScore: 6, maxScore: Infinity }
};

/**
 * Builds a single-signal-type scenario that escalates step by step and
 * stops right at the requested level. Every step's cumulative score is
 * attached (step.cumulative) so the UI can show "score is about to
 * become X" before it's even sent.
 */
function buildCustomScenario(signalType, targetLevel) {
  const meta = SIGNAL_TYPE_META[signalType];
  const safeSteps = SAFE_STEPS[signalType] || [];
  const ladder = ESCALATION_LADDERS[signalType] || [];
  const target = TIER_LEVEL_META[targetLevel];

  const steps = safeSteps.map(s => ({ ...s, signalType }));
  let cumulative = 0;

  if (targetLevel !== 'safe') {
    for (const rung of ladder) {
      cumulative += rung.weight;
      steps.push({ ...rung, signalType, cumulative });
      if (cumulative >= target.minScore) break; // stop right at the requested tier
    }
  }

  return {
    label: `${meta.label} -- build up to: ${target.label}`,
    description: targetLevel === 'safe'
      ? `Only ordinary, unremarkable ${meta.label.toLowerCase()} -- demonstrates the system stays quiet on normal activity.`
      : `Starts with ordinary ${meta.label.toLowerCase()}, then escalates one step at a time using only ${signalType} signals, stopping right after the score crosses into ${target.label.toLowerCase()}.`,
    steps: steps.map(s => ({
      speaker: meta.speakerFor ? meta.speakerFor() : 'child',
      signalType,
      content: s.content,
      note: s.note
    }))
  };
}

// ---------------------------------------------------------------------
// GUIDED STORY MODE (original scenarios -- kept as-is)
// ---------------------------------------------------------------------
// All scenarios below are entirely fictional/scripted -- no real people,
// no real chat platforms, no real messages from anyone. Each step is
// replayed through the real backend (POST /api/signals) so the score,
// tier, and AI explanation you see are the system's actual output, not
// a mocked-up UI.
//
// step shape: { speaker: 'stranger' | 'child' | 'system', signalType, content, note }
//   - speaker only affects how the message renders in the chat pane
//   - signalType/content are what actually gets sent to the backend

const SCENARIOS = {
  grooming_demo: {
    label: 'Suspicious contact pattern (multi-signal story)',
    description: 'A fictional new online contact gradually escalates from friendly small talk to asking for identifying info and pushing to move platforms. Mixes search + chat signals, the way a real evening would.',
    steps: [
      {
        speaker: 'stranger', signalType: 'chat_text',
        content: "hii!! saw ur comment on that game clip, you're really good at this",
        note: 'Ordinary friendly opener -- expected to score 0.'
      },
      {
        speaker: 'child', signalType: 'search_query',
        content: 'how to hide browser history from parents',
        note: "Concealment search -- this one is the CHILD's own action, weight +2."
      },
      {
        speaker: 'stranger', signalType: 'chat_text',
        content: "you're so mature for your age, most people your age wouldn't get it",
        note: 'Grooming-pattern flattery -- weight +3.'
      },
      {
        speaker: 'stranger', signalType: 'chat_text',
        content: "what's your real name btw, and where do you go to school?",
        note: 'Personal info request -- weight +3. Cumulative score should now cross the tier-3 threshold.'
      },
      {
        speaker: 'stranger', signalType: 'chat_text',
        content: "let's talk on a different app instead, and don't tell your parents we've been chatting",
        note: 'Platform switch + secrecy -- weight +3, reinforces the open tier-3 alert.'
      }
    ]
  },

  scam_demo: {
    label: 'Scam / phishing link pattern (multi-signal story)',
    description: 'A fictional sequence of a scam search followed by visits to unconfirmed prize-claim style sites.',
    steps: [
      {
        speaker: 'child', signalType: 'search_query',
        content: 'free robux generator no human verification',
        note: 'Scam-adjacent search -- weight +1.'
      },
      {
        speaker: 'child', signalType: 'url_visit',
        content: 'https://claim-your-prize-now.xyz/robux',
        note: 'Unconfirmed scam-pattern URL -- weight +2.'
      },
      {
        speaker: 'child', signalType: 'url_visit',
        content: 'https://verify-your-account-freevbucks.top/',
        note: 'Another unconfirmed scam-pattern URL -- weight +2.'
      },
      {
        speaker: 'child', signalType: 'url_visit',
        content: 'https://you-have-won-a-prize.club/claim',
        note: 'Third one -- cumulative score should now cross the tier-3 threshold.'
      }
    ]
  },

  control_demo: {
    label: 'Normal evening (control -- should NOT alert)',
    description: 'Ordinary, unremarkable activity. Demonstrates that the system does not raise false alarms on normal browsing and chatting.',
    steps: [
      {
        speaker: 'child', signalType: 'search_query',
        content: 'fractions homework help grade 6',
        note: 'Ordinary homework search -- expected to score 0 and not even be saved.'
      },
      {
        speaker: 'stranger', signalType: 'chat_text',
        content: 'hey are we still doing the group project tonight',
        note: 'A classmate confirming plans -- expected to score 0.'
      },
      {
        speaker: 'child', signalType: 'chat_text',
        content: 'yeah! see you at 6, I finished my part already',
        note: "Expected to score 0."
      },
      {
        speaker: 'child', signalType: 'url_visit',
        content: 'https://www.khanacademy.org/math/pre-algebra',
        note: 'Ordinary educational site -- expected to score 0 and not be saved, thanks to the URL-risk heuristic (a plain "not confirmed malicious" is not the same as suspicious).'
      }
    ]
  }
};
