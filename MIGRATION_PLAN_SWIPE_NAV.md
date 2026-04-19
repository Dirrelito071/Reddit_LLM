#
# Additional Review Notes & Safeguards (2026-04-19)

## Lessons Learned from Previous Attempt

- Overlapping old and new logic (e.g., not fully removing .on class toggling, or leaving duplicate event handlers) caused breakage.
- Duplicated or conflicting DOM elements (like multiple .tabs or <main> sections) led to confusion and bugs.
- CSS conflicts between display: none/block and flex/transform approaches broke layout and navigation.
- Incomplete migration of all tab/pane update logic (e.g., not updating tab highlights or scroll positions in all cases) left the UI in an inconsistent state.
- Subtle bugs in touch/mouse event handling, especially on different devices, were hard to debug.

## Extra Safeguards for This Migration

- **Explicit “No Duplication” Checkpoints:**
	- After each removal or refactor step, search for and remove any duplicate event listeners, DOM elements, or CSS rules (e.g., grep for .on, .pane, .tabs).
- **Manual Testing Checklist for Each Step:**
	- After each step: open the app, click all tabs, swipe on mobile, resize window, check for errors in the browser console.
- **Version Control Discipline:**
	- Commit after every successful step, with clear messages. Never proceed to the next step if the current one is not fully working and committed.
- **Feature Flags (Optional):**
	- For major changes, consider using a feature flag or toggle to switch between old and new navigation, allowing for easier rollback and comparison.
- **Peer Review or Pair Programming:**
	- If possible, have another developer review each step, especially the removal of legacy code and the introduction of new event logic.
- **Automated Linting/Formatting:**
	- Run linters and formatters after each step to catch syntax or style issues early.
- **Edge Case Testing:**
	- Explicitly test with 0, 1, and many tabs/panes. Test on slow devices or emulators to catch performance issues.

## Summary

The plan is well-structured, but the most common source of breakage is overlapping old and new logic, especially with event listeners and DOM structure. Be ruthless in removing legacy code before adding new logic. Always keep the UI in a working state after each step, even if the new feature isn’t fully implemented yet. If a step feels too big, break it down further.

**Keep these notes in mind and update this file as you progress.**
# Migration Plan: Real-Time Flex-Based Swipe/Peek Navigation for Reddit LLM

## Objective
Transform the current tab/pane navigation system from class-based show/hide logic to a modern, real-time, flex-based swipe/peek system with smooth animations, mobile-friendly gestures, and robust code structure.

---

## Stepwise Migration Plan

### 1. Preparation & Baseline
- [ ] Review and document all current navigation-related code (JS, CSS, HTML structure).
- [ ] Identify all places where `.on` class, display toggling, and tab/pane logic are used.
- [ ] List all event listeners and DOM elements related to navigation.
- [ ] Ensure a working backup/commit of the current state.

### 2. Clean Up Legacy Code
- [ ] Remove duplicate or unused DOM elements (e.g., extra `.tabs`, `<main>`, or `.panes-track`).
- [ ] Remove all legacy `.on` class toggling and display: none/block logic for panes.
- [ ] Remove or refactor any redundant event listeners or functions.
- [ ] Test: Navigation should still work with only the minimal, clean legacy logic.

### 3. Refactor HTML Structure
- [ ] Ensure a single `.tabs` container and a single `.panes-track` flex container inside `#panes-container`.
- [ ] Each pane should be a direct child of `.panes-track` and use `flex: 0 0 100%`.
- [ ] Test: All panes render side-by-side in the DOM.

### 4. CSS Refactor for Flex/Transform
- [ ] Update `.panes-track` to use `display: flex; transition: transform ...;`.
- [ ] Remove any CSS that toggles display: none/block for panes.
- [ ] Add/adjust CSS for smooth transform transitions and visual feedback (e.g., .pane-dragging, box-shadow, scale).
- [ ] Test: Panes are visible and styled correctly.

### 5. Implement Real-Time Swipe/Peek Logic
- [ ] Add JS to handle touch/mouse drag events on `#panes-container`.
- [ ] On drag, update `.panes-track` transform in real time to follow the finger/mouse.
- [ ] Add resistance at edges (no infinite looping yet).
- [ ] On release, snap to the nearest pane with animation.
- [ ] Test: Swiping left/right animates the panes smoothly.

### 6. Tab Bar Scroll & Centering
- [ ] Refactor tab click logic to update `.panes-track` transform instead of toggling classes.
- [ ] Implement scrollTabIntoCenter to animate the tab bar so the selected tab is centered.
- [ ] Test: Clicking a tab animates both the panes and the tab bar.

### 7. Visual Feedback & Accessibility
- [ ] Add visual feedback during drag (e.g., .pane-dragging, scale, shadow).
- [ ] Ensure ARIA roles and keyboard navigation are preserved or improved.
- [ ] Test: Visual feedback is clear and accessible.

### 8. Looping & Edge Resistance (Optional)
- [ ] Optionally, implement looping navigation (swiping past last pane goes to first, and vice versa).
- [ ] Otherwise, ensure strong resistance at edges.
- [ ] Test: Looping or resistance works as intended.

### 9. Remove All Legacy Navigation Code
- [ ] Remove any remaining legacy navigation code, comments, or CSS.
- [ ] Test: Only the new flex/transform-based logic is present.

### 10. Comprehensive Testing
- [ ] Test on desktop and mobile (touch and mouse).
- [ ] Test with many/few tabs, long/short tab names, and different screen sizes.
- [ ] Test accessibility (keyboard, screen reader, ARIA roles).
- [ ] Test performance and responsiveness.
- [ ] Test error handling and edge cases (e.g., resizing, rapid swipes).

### 11. Documentation & Maintenance
- [ ] Document all new functions, CSS classes, and event flows in code comments.
- [ ] Update README or relevant docs to describe the new navigation system.
- [ ] Add a migration note for future maintainers.

---

## Key Principles
- **Incremental changes:** Only one major change per step, with testing after each.
- **No duplication:** Remove legacy code before adding new logic.
- **Test-driven:** Manual or automated tests after each step.
- **Accessibility:** Maintain or improve ARIA/keyboard support.
- **Mobile-first:** Prioritize touch and mobile UX.

---

## Rollback Plan
- At any step, if a regression or major bug is found, revert to the last working commit.
- Keep detailed commit messages for each migration step.

---

## Checklist for Each Step
- [ ] Code is clean and free of duplication.
- [ ] All navigation works as expected.
- [ ] No console errors or warnings.
- [ ] UI/UX is smooth and visually consistent.
- [ ] Accessibility is preserved.

---

## File: MIGRATION_PLAN_SWIPE_NAV.md
This file should be kept up to date as you progress through the migration. Mark each step as complete and note any deviations or issues encountered.
