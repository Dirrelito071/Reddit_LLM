# Swipeable Subreddit Navigation with Looping and Animation

## Objective
Enable users to switch between subreddit summaries by swiping left/right on the summaries section, in addition to tapping the tabs. Swiping should loop (wrap) between the first and last subreddit, and transitions should be animated for a native mobile feel.

---

## Implementation Plan

### 1. Discovery & Design
- **Review Structure:**
  - Inspect `news-digest.html` for tab and pane structure.
  - Identify the DOM element for swipe detection (likely `#panes-container` or `.pane`).
- **Decide on Approach:**
  - Use vanilla JS for touch event handling (no external dependencies).
  - Use CSS transitions for sliding animation.

### 2. Swipe Detection Logic
- **Add Event Listeners:**
  - Attach `touchstart`, `touchmove`, and `touchend` listeners to the summaries section.
- **Track Touches:**
  - On `touchstart`, record the initial X position.
  - On `touchmove`, track the current X position.
  - On `touchend`, calculate the horizontal distance and direction.
- **Threshold:**
  - Only trigger a swipe if the horizontal movement exceeds a set threshold (e.g., 40px) and is greater than vertical movement.

### 3. Tab Switching Logic
- **Determine Current Index:**
  - Track the current active subreddit index in the JS state.
- **Looping:**
  - Swiping left on the last subreddit wraps to the first.
  - Swiping right on the first subreddit wraps to the last.
- **Update UI:**
  - Programmatically activate the corresponding tab and pane.
  - Ensure tab highlight, badge, and content update as with click navigation.

### 4. Animation
- **CSS Transitions:**
  - Add a CSS class for sliding transitions (e.g., `.pane-slide-left`, `.pane-slide-right`).
  - On swipe, apply the appropriate class to animate the outgoing and incoming panes.
  - Remove the animation class after the transition completes to reset state.
- **Accessibility:**
  - Ensure keyboard navigation and screen reader support are unaffected.

### 5. Integration
- **Sync with Tab Clicks:**
  - Ensure that clicking a tab or swiping both update the active index and UI consistently.
- **Edge Cases:**
  - Prevent accidental tab switches on vertical scroll or minor drags.
  - Handle rapid swipes and prevent animation glitches.

### 6. Verification
- **Test on Devices:**
  - Test on mobile browsers and desktop browsers with touch emulation.
- **Check Looping:**
  - Verify that swiping left/right on the edges loops as expected.
- **Check Animation:**
  - Ensure smooth transitions and no flicker or jump.
- **Accessibility:**
  - Confirm keyboard and screen reader navigation still work.

---

## Relevant Files
- `news-digest.html` — Add touch event logic, update tab/pane switching JS, add CSS for animation.

## Decisions
- Use vanilla JS for touch events and state management.
- Use CSS transitions for animation.
- No backend changes required.

## Further Considerations
- Optionally, add visual feedback (e.g., shadow or scale) during swipe.
- Consider debouncing or locking swipes during animation to prevent rapid-fire transitions.

---

## Example CSS (for reference)
```css
.pane-slide-left {
  animation: slideLeft 0.3s forwards;
}
.pane-slide-right {
  animation: slideRight 0.3s forwards;
}
@keyframes slideLeft {
  from { transform: translateX(0); }
  to { transform: translateX(-100%); }
}
@keyframes slideRight {
  from { transform: translateX(0); }
  to { transform: translateX(100%); }
}
```

---

## Summary
This plan will deliver a mobile-friendly, swipeable, and animated subreddit navigation experience, with looping and smooth transitions, using only frontend changes in `news-digest.html`.