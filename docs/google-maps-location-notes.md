# Google Maps Location Notes

## Concise Summary

Umamimatch already has a clear team-based decision flow, but it does not yet store or use structured location data. Google Maps APIs could improve both decision quality and UX by adding restaurant coordinates, team anchor locations, distance or travel-time scoring, and map-based visualizations for current options and past decisions.

## Potential Ideas

- Enrich restaurants during ingest with Google Places data such as `place_id`, formatted address, latitude/longitude, rating, and opening status.
- Add a team anchor location such as office or meetup point and use it during lunch decisions.
- Let users optionally store a preferred start location or max walking time in their profile preferences.
- Include distance and travel time in the agent inputs so recommendations are based on both menu fit and convenience.
- Show candidate restaurants on a map on the team decision page.
- Show the final recommendation on a map with route context and travel estimate.
- Add mini-maps or location summaries to decision history and dashboard views.

## Open Issues for Implementation

- Choose the source of truth for location:
  - `Restaurant.meta` and `Profile.other_preferences` are fast to start with.
  - Dedicated DB columns are better if distance becomes core ranking logic.
- Decide whether location should be team-first or user-first:
  - Team anchor is simpler and fits the current decision flow.
  - Per-user origins are more accurate but require fairness and privacy decisions.
- Decide which Google APIs are actually needed:
  - Places API for enrichment and autocomplete.
  - Geocoding API if addresses need normalization.
  - Distance Matrix or Routes API for travel time.
  - Maps JavaScript API for frontend rendering.
- Define when enrichment runs:
  - On restaurant ingest only.
  - On manual refresh.
  - Periodic refresh for stale business metadata.
- Define what the agent should consume:
  - Raw coordinates only.
  - Precomputed travel times.
  - Hard filters such as max walking distance plus LLM reasoning.
- Decide where to persist decision-time geo context:
  - Save chosen restaurant location in `DecisionRun.result`.
  - Optionally save ranked candidates with distance metrics for history visualizations.
- Add environment and secret handling for Maps keys separately from current Google Cloud provider config.

## Open Issues in Current Code

- No first-class location model exists today:
  - `Restaurant` only has `url`, `display_name`, and `meta`.
  - `Team` has no office or meetup location.
  - `Profile` has no typed location fields.
- The agent tools do not expose any location context:
  - `retrieve_team_needs` returns dietary and budget data only.
  - `retrieve_restaurant_menus` returns menu and freshness data only.
- Decision results do not persist geo information, so map-based history is not available.
- Frontend decision UI has no map-ready types in `frontend/lib/types.ts`.
- Team detail page has no place to configure a team anchor location.
- Profile form has no location or travel-preference fields.
- The team decision page still calls a likely missing endpoint:
  - `POST /restaurants/{id}/rescrape?force=true`
- The team decision page removes restaurants via the global delete endpoint instead of the team-scoped remove endpoint:
  - Current call: `DELETE /restaurants/{restaurant_id}`
  - Team API already exists for scoped removal: `DELETE /api/teams/{team_id}/restaurants/{restaurant_id}`
- There is also a stale frontend form still wired to an old decision flow:
  - `frontend/components/forms/RestaurantUrlForm.tsx`

## Suggested Next Step

Start with the smallest coherent slice:

1. Add restaurant location enrichment on ingest.
2. Add a team anchor location.
3. Pass distance or travel-time data into the decision tools.
4. Render a simple restaurant map on the team decision page.

## Start Plan

## Phase 0: Google Maps Setup First

Goal: enable Google Maps Platform and inspect real responses before designing ingest.

- Create or choose the Google Cloud project for Umamimatch.
- Enable the minimum APIs:
  - Places API (New)
  - Maps JavaScript API
  - Routes API
- Create API keys:
  - backend key for Places and Routes
  - frontend key for Maps JavaScript API
- Apply key restrictions:
  - backend key restricted by API
  - frontend key restricted by HTTP referrer
- Add local env vars for:
  - backend Places or Routes key
  - frontend Maps JavaScript key
- Make one manual test request to Places Text Search (New) for a real restaurant.
- Inspect the returned fields and confirm which ones should be persisted.
- Make one manual test request to Place Details (New) using the returned `placeId`.
- Optionally make one manual Autocomplete test for a team office or meetup address.

Acceptance criteria:

- Google Maps project is enabled and keys exist.
- One real restaurant can be resolved through Places.
- The team knows the exact raw fields available from Google before implementing ingest.

## Phase 1: Scope and Decisions

Goal: lock a minimal first slice before writing code.

- Choose first use case:
  - Recommended: team anchor location plus restaurant map pins.
- Choose first APIs:
  - Recommended: Places API and Maps JavaScript API.
- Choose first location model:
  - Recommended: dedicated team location fields and restaurant location in `Restaurant.meta`.
- Choose first ranking rule:
  - Recommended: expose distance to the agent, but do not hard-filter yet.

Acceptance criteria:

- Team has one anchor location.
- Restaurants can store coordinates and address.
- Frontend can render a simple map without decision scoring changes yet.

## Phase 2: Backend Foundation

Goal: create stable data seams for location.

- Add team location fields:
  - `meeting_address`
  - `meeting_place_id`
  - `meeting_lat`
  - `meeting_lng`
- Extend team read and update schemas to expose these fields.
- Add restaurant location shape in `Restaurant.meta` for:
  - `place_id`
  - `formatted_address`
  - `lat`
  - `lng`
  - optional rating and opening status
- Add config entries for Google Maps API keys.

Acceptance criteria:

- Team detail API returns location fields.
- Team update API can save location fields.
- Restaurant records can persist normalized location metadata.

## Phase 3: Restaurant Enrichment

Goal: enrich restaurants with location data during ingest.

- Add a small Google Maps service module in backend.
- On `POST /decision/ingest-restaurants`, resolve restaurant location after URL creation.
- Match by restaurant name, domain, or scraped page title with fallback handling.
- Save enrichment results into `Restaurant.meta`.
- Add safe failure behavior:
  - menu ingest must still work if Maps enrichment fails.

Acceptance criteria:

- Newly ingested restaurants store location metadata when found.
- Ingest endpoint remains functional without blocking on Maps failures.
- Existing restaurants can be backfilled later.

## Phase 4: Team UI Setup

Goal: let the team define a shared decision origin.

- Add team location edit controls on the team detail page.
- Use Google Places autocomplete for office or meetup selection.
- Show saved team anchor location in the team summary.
- Add frontend types for team and restaurant location fields.

Acceptance criteria:

- Team creator can set and update a team anchor location.
- Team detail page shows the saved location cleanly.

## Phase 5: First Visualization

Goal: show useful location context before changing decision logic.

- Add a map component on the team decision page.
- Show:
  - team anchor pin
  - restaurant pins
  - selected restaurant highlight after decision
- Add a compact location summary in the restaurant list:
  - address
  - distance from team anchor if available

Acceptance criteria:

- Team decision page renders the team anchor and available restaurants on a map.
- Recommendation card can highlight the chosen restaurant on the map.

## Phase 6: Decision Enrichment

Goal: make location affect recommendations.

- Extend `retrieve_team_needs` to include team anchor context.
- Extend `retrieve_restaurant_menus` or add a new tool to include:
  - address
  - lat/lng
  - distance from team anchor
  - optional travel time
- Update prompt guidance so the agent weighs convenience with dietary fit.
- Save geo context in `DecisionRun.result` for history use.

Acceptance criteria:

- Agent input includes structured location context.
- Decision result stores chosen restaurant location and distance metadata.

## Phase 7: Cleanup and Follow-up

Goal: remove blockers and prepare for broader rollout.

- Fix stale rescrape call on the team decision page.
- Switch team restaurant removal to the team-scoped delete endpoint.
- Remove or refactor the old `RestaurantUrlForm` flow.
- Add a small backfill script for old restaurants with no geo metadata.
- Add dashboard and history visualizations only after the core team decision flow works.

Acceptance criteria:

- Team decision page uses correct APIs.
- Old restaurant data can be enriched without re-entering URLs.

## Recommended First Sprint

If time is tight, do only this:

1. Add team location fields to backend and frontend.
2. Add a Google Places autocomplete input on the team page.
3. Enrich restaurants with lat/lng during ingest.
4. Render a simple map with pins on the team decision page.

This gives a visible demo quickly and keeps the decision engine unchanged until the data layer is stable.

## Discovery-First View

Before finalizing ingest, it makes sense to look at Google Maps as a discovery and normalization layer.

- Places API (New) is the core discovery API.
- Maps JavaScript API is mainly for rendering.
- Routes API is for distance and travel time after places are known.

That means the right order is:

1. Discover candidate places.
2. Normalize them into one saved restaurant location.
3. Only then compute travel metrics and render maps.

## What Google API Gives Us

### Places API (New)

Best fit for restaurant discovery and enrichment.

Useful outputs from Text Search and Place Details include:

- `id` and `name`
  - stable Google place identifiers
- `displayName`
  - user-facing place name
- `formattedAddress` and `shortFormattedAddress`
  - normalized address text
- `location`
  - latitude and longitude
- `googleMapsUri`
  - direct deep link to Google Maps
- `primaryType` and `types`
  - place classification such as restaurant or cafe
- `rating` and `userRatingCount`
  - social proof for future ranking
- `regularOpeningHours` or `currentOpeningHours`
  - availability context
- `websiteUri`
  - useful to compare against the scraped URL
- `photos`
  - optional for richer UI later

### Autocomplete (New)

Best fit for team location setup and manual correction flows.

Useful outputs include:

- `placeId`
- `text`
- structured display text
- place type hints

This is ideal when a user sets the team office or meetup point.

### Routes API

Best fit after the app already knows the team origin and restaurant coordinates.

Useful outputs include:

- `distanceMeters`
- `duration`

This is what should feed ranking and map annotations later.

## How This Should Change Ingest Design

Restaurant ingest should not treat Google Maps as a rendering feature only. It should treat it as a place-resolution step.

Recommended ingest flow:

1. User submits a restaurant menu URL.
2. Backend scrapes menu content as it does today.
3. Backend derives discovery hints from the URL and page content:
   - domain
   - scraped title
   - detected restaurant name
   - detected address or phone number if present
4. Backend calls Places Text Search (New) to find candidate places.
5. Backend chooses the best candidate using confidence rules.
6. Backend optionally calls Place Details (New) for the chosen `placeId`.
7. Backend stores normalized location data on the restaurant record.

Recommended fields to persist from Google:

- `google_place_id`
- `google_display_name`
- `google_formatted_address`
- `google_lat`
- `google_lng`
- `google_maps_uri`
- `google_primary_type`
- `google_rating`
- `google_user_rating_count`
- `google_website_uri`
- `google_last_enriched_at`
- `google_match_confidence`

## Recommended Matching Strategy

Do not blindly trust the first Google result.

Use a simple confidence model:

- Strong match:
  - website domain matches restaurant site
  - display name is very close to scraped title
  - address found in page content is close to Google result
- Medium match:
  - name matches but website is missing
  - result type is restaurant, cafe, or similar
- Low match:
  - only fuzzy name similarity
  - no website or address match

Behavior by confidence:

- High confidence:
  - save automatically
- Medium confidence:
  - save but mark as reviewable
- Low confidence:
  - do not overwrite location automatically

## Better Starting Plan

Given what Google APIs return, a better first implementation order is:

1. Build a backend `places_service` wrapper for Text Search and Place Details.
2. Add restaurant location persistence.
3. Enrich restaurants during ingest using Google Places.
4. Add team location selection with Autocomplete.
5. Add first map rendering.
6. Add Routes API distance or travel-time scoring.

This order is safer because it lets the data model be shaped by real Google place responses before you commit to frontend map behavior.

## Practical Recommendation

The smallest useful spike is not a map.

It is:

1. Set up Google Maps Platform keys and enable the APIs.
2. Take one existing restaurant URL.
3. Extract a likely restaurant name from it.
4. Run one Places Text Search request.
5. Inspect the returned fields.
6. Define the exact restaurant location payload the app should store.

Once that payload is stable, the rest of the implementation becomes much easier.

## Step 0 Checklist

Use this before any backend or frontend coding.

1. Create Google Cloud project or confirm existing project ownership.
2. Enable:
   - Places API (New)
   - Maps JavaScript API
   - Routes API
3. Create two API keys:
   - `GOOGLE_MAPS_SERVER_API_KEY`
   - `NEXT_PUBLIC_GOOGLE_MAPS_API_KEY`
4. Restrict the server key to server-side APIs only.
5. Restrict the frontend key to allowed local and deployed origins.
6. Test Places Text Search with one restaurant query.
7. Test Place Details with the returned `placeId`.
8. Write down the final field list to persist in Umamimatch.

Recommended first persisted fields:

- `place_id`
- `display_name`
- `formatted_address`
- `location`
- `google_maps_uri`
- `primary_type`
- `website_uri`
- `rating`
- `user_rating_count`
- `last_enriched_at`
