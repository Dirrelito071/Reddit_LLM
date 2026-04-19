# Settings Panel Implementation - Complete

## Overview
The Settings panel has been fully implemented across all layers:
- **Database layer** (db.py): Settings persistence
- **API layer** (news-server2.py): REST endpoints for settings management
- **Frontend layer** (news-digest.html): User interface with modal

## Implementation Details

### 1. Database Layer (db.py)
**New Table**: `user_settings`
```sql
CREATE TABLE IF NOT EXISTS user_settings (
    setting_key TEXT PRIMARY KEY,
    setting_value TEXT NOT NULL,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
```

**New Functions**:
- `get_setting(key, default=None)` - Retrieve setting from database
- `set_setting(key, value)` - Store setting in database
- `get_subreddits()` - Returns list from DB or defaults to config.SUBREDDITS
- `set_subreddits(subreddit_list)` - Validates and stores subreddit list (JSON format)
- `get_llm_question()` - Returns custom question or hardcoded default
- `set_llm_question(question)` - Validates and stores LLM question

**Validation**:
- Subreddits: Minimum 1 required, stored as JSON array
- LLM Question: Non-empty string required

### 2. API Layer (news-server2.py)
**Updated Endpoints**:

#### GET /api/status
**Old Response**:
```json
{
  "running": false,
  "subreddits": { "category1": {...}, "category2": {...} }
}
```

**New Response**:
```json
{
  "running": false,
  "subreddits": ["DigitalAudioPlayer", "longboarding"],
  "llm_question": "Summarize the following Reddit posts",
  "status": { "category1": {...}, "category2": {...} }
}
```

**New Endpoints**:

##### POST /api/settings/subreddits
Request body:
```json
{
  "subreddits": ["programming", "learnprogramming"]
}
```
Response:
```json
{
  "success": true,
  "message": "Subreddits updated successfully"
}
```
Validation: Minimum 1 subreddit required

##### POST /api/settings/question
Request body:
```json
{
  "question": "What are the key takeaways from this post?"
}
```
Response:
```json
{
  "success": true,
  "message": "Question updated successfully"
}
```
Validation: Non-empty question required

**Pipeline Integration**:
- `run_pipeline()` now calls `db.get_subreddits()` to load user-configured subreddits
- Settings persist across container restarts

### 3. Frontend Layer (news-digest.html)

#### UI Components
- **Settings Button**: ⚙️ icon in header (next to Pipeline button)
- **Settings Modal**: Hidden by default, shown when button clicked
- **Tab Navigation**: Two tabs - "Subreddits" and "LLM Question"
- **Error Display**: Inline error messages with validation feedback

#### Subreddits Tab
- Displays current monitored subreddits
- Add new subreddit: input field + "Add" button
- Remove subreddit: × button on each subreddit item
- Validation:
  - Minimum 1 subreddit required
  - No duplicate subreddits
  - Max 100 characters per subreddit name

#### LLM Question Tab
- Textarea for editing LLM question
- Pre-populated from database on modal open
- Keyboard shortcut: Cmd+Enter (Mac) or Ctrl+Enter (Windows) to save

#### JavaScript Functions
- `openSettings()` - Display modal, load current settings
- `closeSettings()` - Hide modal, clear input
- `switchTab(tabName)` - Switch between tabs
- `loadCurrentSettings()` - Fetch settings from /api/status
- `renderSubredditList(subreddits)` - Render subreddit items with remove buttons
- `addSubreddit()` - Add subreddit to list with validation
- `removeSubredditFromList(subreddit)` - Remove subreddit from UI
- `saveSettings()` - POST both subreddits and question to API
- `showSettingsError(message)` - Display error in red
- `showSettingsSuccess(message)` - Display success in green
- `clearSettingsError()` - Hide error message
- `escapeHtml(text)` - Sanitize HTML to prevent XSS

#### Keyboard Shortcuts
- **Enter** in subreddit input: Add subreddit
- **Cmd+Enter** or **Ctrl+Enter** in question textarea: Save settings
- **Escape**: Close modal (click outside modal also works)

#### Event Handlers
- Settings button click → open modal
- Close button/Cancel button click → close modal
- Modal background click → close modal
- Tab button click → switch tab
- Add button click → add subreddit
- Remove button click → remove subreddit
- Save button click → persist all settings

### 4. CSS Styling
- `.modal-overlay`: Fixed overlay background
- `.modal-content`: Centered modal box
- `.settings-tabs`: Tab navigation bar
- `.settings-tab`: Individual tab button (with active state)
- `.settings-content`: Tab content area
- `.subreddit-list`: Container for subreddit items
- `.subreddit-item`: Individual subreddit with remove button
- `.form-group`: Form element grouping
- `.modal-buttons`: Save/Cancel button container
- `.add-subreddit`: Inline add subreddit form
- Error message styling: #ffebee background, #f44336 text (red)
- Success message styling: #4caf50 text (green)

## Usage Flow

1. **User clicks Settings (⚙️) button**
   - Modal opens
   - Current subreddits loaded from API
   - Current LLM question loaded from API
   - Subreddits tab shown by default

2. **User adds subreddit**
   - Types subreddit name in input
   - Clicks "Add" button or presses Enter
   - Item added to list with remove button
   - Input cleared

3. **User removes subreddit**
   - Clicks × button on subreddit item
   - Item removed from list

4. **User edits LLM question**
   - Clicks "LLM Question" tab
   - Edits textarea
   - Can use Cmd+Enter to save quickly

5. **User saves settings**
   - Clicks "Save Settings" button
   - POST requests sent to both endpoints
   - Success message displayed
   - Modal closes after 1 second

6. **User cancels**
   - Clicks "Cancel" button or close button
   - Modal closes without saving changes
   - Next pipeline run uses updated settings (or unchanged if cancelled)

## Database Persistence
- Settings stored in `user_settings` table
- Survive container restarts
- JSON format for arrays (subreddits)
- Key-value storage with timestamp

## Error Handling
- Input validation at frontend (before API call)
- Input validation at backend (API)
- Error messages displayed to user
- Invalid requests rejected with HTTP 400/error JSON

## Testing Checklist
- [ ] Settings button opens modal
- [ ] Subreddits tab displays current subreddits
- [ ] LLM Question tab displays current question
- [ ] Add subreddit validation works (no empty, no duplicates)
- [ ] Remove subreddit removes from list
- [ ] Save button POSTs to both API endpoints
- [ ] Settings persist after container restart
- [ ] Pipeline uses new settings on next run
- [ ] Error messages display for invalid input
- [ ] Success message displays after save
- [ ] Modal closes automatically after save
- [ ] Keyboard shortcuts work (Enter, Cmd+Enter)

## Files Modified
1. **db.py**: Added user_settings table and 6 new functions
2. **news-server2.py**: Updated /api/status, added 2 new endpoints, modified pipeline
3. **news-digest.html**: Added Settings modal UI and JavaScript event handlers

## Backwards Compatibility
- API response includes both new fields (`subreddits` list, `llm_question`) and old format (`status`)
- Frontend applyStatus() checks for `data.status` first, falls back to `data.subreddits`
- Default subreddits from config.py used if database empty
- Pipeline still works with or without database settings
