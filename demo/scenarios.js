// All scenarios below are entirely fictional/scripted — no real people,
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
    label: 'Suspicious contact pattern (demo)',
    description: 'A fictional new online contact gradually escalates from friendly small talk to asking for identifying info and pushing to move platforms.',
    steps: [
      {
        speaker: 'stranger', signalType: 'chat_text',
        content: "hii!! saw ur comment on that game clip, you're really good at this",
        note: 'Ordinary friendly opener — expected to score 0.'
      },
      {
        speaker: 'child', signalType: 'search_query',
        content: 'how to hide browser history from parents',
        note: 'Concealment search — this one is the CHILD\'s own action, weight +2.'
      },
      {
        speaker: 'stranger', signalType: 'chat_text',
        content: "you're so mature for your age, most people your age wouldn't get it",
        note: 'Grooming-pattern flattery — weight +3.'
      },
      {
        speaker: 'stranger', signalType: 'chat_text',
        content: "what's your real name btw, and where do you go to school?",
        note: 'Personal info request — weight +3. Cumulative score should now cross the tier-3 threshold.'
      },
      {
        speaker: 'stranger', signalType: 'chat_text',
        content: "let's talk on a different app instead, and don't tell your parents we've been chatting",
        note: 'Platform switch + secrecy — weight +3, reinforces the open tier-3 alert.'
      }
    ]
  },

  scam_demo: {
    label: 'Scam / phishing link pattern (demo)',
    description: 'A fictional sequence of a scam search followed by visits to unconfirmed prize-claim style sites.',
    steps: [
      {
        speaker: 'child', signalType: 'search_query',
        content: 'free robux generator no human verification',
        note: 'Scam-adjacent search — weight +1.'
      },
      {
        speaker: 'child', signalType: 'url_visit',
        content: 'https://claim-your-prize-now.xyz/robux',
        note: 'Unconfirmed scam-pattern URL — weight +2.'
      },
      {
        speaker: 'child', signalType: 'url_visit',
        content: 'https://verify-your-account-freevbucks.top/',
        note: 'Another unconfirmed scam-pattern URL — weight +2.'
      },
      {
        speaker: 'child', signalType: 'url_visit',
        content: 'https://you-have-won-a-prize.club/claim',
        note: 'Third one — cumulative score should now cross the tier-3 threshold.'
      }
    ]
  },

  control_demo: {
    label: 'Normal evening (control — should NOT alert)',
    description: 'Ordinary, unremarkable activity. Demonstrates that the system does not raise false alarms on normal browsing and chatting.',
    steps: [
      {
        speaker: 'child', signalType: 'search_query',
        content: 'fractions homework help grade 6',
        note: 'Ordinary homework search — expected to score 0 and not even be saved.'
      },
      {
        speaker: 'stranger', signalType: 'chat_text',
        content: 'hey are we still doing the group project tonight',
        note: 'A classmate confirming plans — expected to score 0.'
      },
      {
        speaker: 'child', signalType: 'chat_text',
        content: 'yeah! see you at 6, I finished my part already',
        note: "Expected to score 0."
      },
      {
        speaker: 'child', signalType: 'url_visit',
        content: 'https://www.khanacademy.org/math/pre-algebra',
        note: 'Ordinary educational site — expected to score 0 and not be saved, thanks to the URL-risk heuristic (a plain "not confirmed malicious" is not the same as suspicious).'
      }
    ]
  }
};
