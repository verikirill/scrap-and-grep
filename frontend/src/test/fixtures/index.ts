// Builders of API payloads for component tests. Each one returns a complete,
// valid object; a test overrides only the fields its behaviour depends on.
// One file per area of the app; tests import them all from here.
//
// Ids: what other objects point at is fixed (user-1, profile-1, interest-1,
// digest-1, bot-1, channel-1, source 1), so defaults match up. Articles, posts,
// suggestions and MCP keys take the next number of a counter, so a list never
// repeats one; read such an id from the built object instead of guessing it.
export * from './account'
export * from './analytics'
export * from './articles'
export * from './channels'
export * from './company'
export * from './digestExtras'
export * from './digests'
export * from './entries'
export * from './feed'
export * from './profiles'
export * from './sources'
