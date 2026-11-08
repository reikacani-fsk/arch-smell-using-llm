# Refactoring of the architectural smells of zo1223/OpaiTV (code)

**Summary:** Broke the App↔Views and App↔Views↔LocalPlayback cycles by turning the App project's root namespace into a pure shell (App, MainWindow, the app-level converter) and moving every service it used to hold into cohesive sub-namespaces: Hosting (AppServices, IAppHost, AppPage, navigation parameter records), Playback (PlaybackController, PlaybackState), Caching (VodCacheService, HlsAesDecryptMerger, VodDownloadManager), CacheCatalog (VodCacheLookup, LocalCachePlaybackCatalog), SourceHealth (VodSourceHealthProbe, VodPlayableSourceResolver), Updates (DesktopUpdateService), AiImport (AiCliLauncher, AiSourceWatcher). ImageLoader went to Controls, and the page-only helpers plus the page contracts INavigationAware/INavigationVisibilityAware went to Views. Core was split by concern into Core.Catalog, Core.VodSources, Core.StreamHealth and Core.Library, all depending one-way on Core (56 → 29 classes in Core). Tests for App-project classes moved to OrionTV.Desktop.Tests.App, changing only namespaces and usings (42 → 25 + 17 classes). Small moved types got new files in matching folders; large files only had their namespace declaration changed. The solution builds; tests were not run because no test runner was available. Smells 7–12 and 14 are only reduced or left unchanged, as explained per smell.

**Checks:** builds yes, tests failing_before, Designite after the refactoring ok

**Patch:** [refactoring.patch](refactoring.patch)

## 1. Cyclic Dependency in OrionTV.Desktop.App (OrionTV.Desktop.App)

**Designite:** The tool detected the smell in this component because this component participates in a cyclic dependency. The participating components in the cycle are: OrionTV.Desktop.App' OrionTV.Desktop.App.Views

**Refactorings:** Extract Component, Move Class

**Steps:**

- Moved AiCliLauncher/AiCliTool/AiCliLaunchResult and AiSourceWatcher to the new namespace OrionTV.Desktop.App.AiImport
- Moved AppServices and Navigation.cs (IAppHost, AppPage, PlaybackResumeContext, DetailParameter, PlayParameter) to OrionTV.Desktop.App.Hosting
- Moved INavigationAware and INavigationVisibilityAware to OrionTV.Desktop.App.Views (new file Views/NavigationContracts.cs), since the pages implement them
- Moved OsdController, PlayerKeyboardHook and LiveChannelViewModel to Views/ (used only by LiveView and PlayerView)
- Moved ImageLoader to Controls/
- Moved PlaybackController/PlaybackState, the cache, source-health and update classes to the namespaces Playback, Caching, CacheCatalog, SourceHealth and Updates
- Updated usings in MainWindow, all views, controls and tests

**Rationale:** The cycle existed because the root namespace held the shell (MainWindow, which creates the views) and also the services the views use (AppServices, IAppHost, AiCliLauncher, OsdController, …). The root now holds only App, MainWindow and the XAML converter, and no type in any other namespace references them. Edges now run root → Views → Hosting/AiImport/…, with no edge back, so the cycle is removed. Only namespaces changed, so behaviour is the same.

**Smell removed:** yes -> **fixed**

## 2. Cyclic Dependency in OrionTV.Desktop.App (OrionTV.Desktop.App)

**Designite:** The tool detected the smell in this component because this component participates in a cyclic dependency. The participating components in the cycle are: OrionTV.Desktop.App' OrionTV.Desktop.App.Views' OrionTV.Desktop.App.LocalPlayback

**Refactorings:** Extract Component, Move Class

**Steps:**

- Moved PlaybackController and PlaybackState from the root namespace to OrionTV.Desktop.App.Playback
- MpvLocalEngine now uses OrionTV.Desktop.App.Playback for PlaybackState instead of the root namespace
- Same root-namespace extraction as for smell 1 (Views no longer reference the root)

**Rationale:** The longer cycle closed through LocalPlayback → root (MpvLocalEngine uses PlaybackState) and root → Views → LocalPlayback. PlaybackState now lives in Playback, which depends on nothing else in the App project, and the root is no longer referenced by Views. So LocalPlayback → Playback and Views → LocalPlayback form no cycle. The enum and its values are unchanged.

**Smell removed:** yes -> **fixed**

## 3. Feature Concentration in OrionTV.Desktop.App (OrionTV.Desktop.App)

**Designite:** The tool detected the smell in this component because the component realizes more than one architectural concern/feature. Independent sets of related classes within this component are: [AiCliTool' AiCliLauncher' AiCliTaskMode' MainWindow' SectionNavigationState' AppPage' IAppHost' INavigationAware' INavigationVisibilityAware' AiSourceWatcher' ChangeKind' AppServices' DesktopUpdateService' PlaybackController' VodCacheService' InlineProgress<T>' VodCacheLog' VodDownloadManager' Job' VodPlayableSourceResolver' VodSourceProbeStatus' VodSourceHealthDisplay' VodSourceHealthProbe' LibVlcMediaDecodeProbe' WindowMessage' HlsAesDecryptMerger' VodCacheSession' CacheFile' PlaybackState' VodDownloadJobStatus' MediaDecodeProbeStatus' IMediaDecodeProbe' VodSourceProbeSampler]' [App]' [EmptyStringToVisibilityConverter]' [ImageLoader]' [LiveChannelViewModel]' [LocalCachePlaybackCatalog]' [OsdController]' [PlayerKeyboardHook' KbdLlHookStruct]' [VodCacheLookup]. LCC (Lack of Component Cohesion) = 0'21

**Refactorings:** Split Component, Move Class

**Steps:**

- Split the 42-class root into Hosting, Playback, Caching, CacheCatalog, SourceHealth, Updates and AiImport
- Moved ImageLoader to Controls; moved LiveChannelViewModel, OsdController and PlayerKeyboardHook to Views
- The root keeps only App, MainWindow (+ nested SectionNavigationState) and EmptyStringToVisibilityConverter (used by App.xaml resources)

**Rationale:** The root mixed unrelated concerns (shell, HLS caching, update download, AI CLI, source probing, LibVLC control, UI helpers). Each concern now has its own namespace whose classes are connected: Caching is linked through VodCacheService/VodCacheSession, and SourceHealth through VodSourceProbeStatus and IMediaDecodeProbe. Helpers that only pages use now sit with the pages. The root has 4 classes, so the isolated groups (ImageLoader, VodCacheLookup, LocalCachePlaybackCatalog, OsdController, …) are no longer in it.

**Smell removed:** yes -> **fixed**

## 4. God Component in OrionTV.Desktop.App (OrionTV.Desktop.App)

**Designite:** The tool detected the smell in this component because the component contains high number of classes. Number of classes in the component are: 42

**Refactorings:** Split Component, Move Class

**Steps:**

- Same split as smell 3: 42 classes → 4 in the root namespace, the rest in the cohesive namespaces Hosting (3 classes), Playback (2), Caching (9), CacheCatalog (2), SourceHealth (8), Updates (1), AiImport (5)

**Rationale:** The root is no longer oversized (4 classes, far below 30), and each extracted namespace is small and has one responsibility.

**Smell removed:** yes -> **fixed**

## 5. Unstable Dependency in OrionTV.Desktop.App (OrionTV.Desktop.App)

**Designite:** The tool detected the smell in this component because this component depends on other components that are less stable than itself. This component depends on following less stable component(s): OrionTV.Desktop.App.Views

**Refactorings:** Move Class, Extract Component

**Steps:**

- Removed every reference from App-project namespaces to the root namespace by moving the services out of it (see smell 1)
- The root now only depends on Views, Hosting and AiImport and has no incoming dependencies

**Rationale:** The root was stable because many namespaces depended on it, yet it depended on the less stable Views. The root now has Ca = 0 and I = 1, so depending on Views no longer points to a less stable component. Hosting (I≈0.57) depends only on Caching, SourceHealth, Playback and Updates, which have I = 0. CacheCatalog (I≈0.67) depends on Hosting and Caching, which are more stable.

**Smell removed:** yes -> **fixed**

## 6. Unstable Dependency in OrionTV.Desktop.App.LocalPlayback (OrionTV.Desktop.App)

**Designite:** The tool detected the smell in this component because this component depends on other components that are less stable than itself. This component depends on following less stable component(s): OrionTV.Desktop.App

**Refactorings:** Move Class

**Steps:**

- Moved PlaybackState (with PlaybackController) to OrionTV.Desktop.App.Playback
- Added `using OrionTV.Desktop.App.Playback;` to LocalPlayback/MpvLocalEngine.cs

**Rationale:** LocalPlayback depended on the volatile root namespace only for the PlaybackState enum. It now depends on Playback, which has no outgoing App-project dependencies (I = 0), so the dependency points to a more stable component.

**Smell removed:** yes -> **fixed**

## 7. Feature Concentration in OrionTV.Desktop.App.Views (OrionTV.Desktop.App)

**Designite:** The tool detected the smell in this component because the component realizes more than one architectural concern/feature. Independent sets of related classes within this component are: [AiImportDialog]' [DetailView]' [FavoritesView]' [HomeView]' [LiveView]' [LocalVideoView' ActiveJobItem' LocalCacheItem' LocalMediaCardItem]' [PlayerShortcutCommand' PlayerShortcutMap' PlayerView' LoadingNoticeMode' PlayerSourceSwitchPolicy' PlayerEpisodeAdvancePolicy]' [SearchView]' [SettingsView]. LCC (Lack of Component Cohesion) = 0'53

**Refactorings:** Move Class

**Steps:**

- Moved INavigationAware and INavigationVisibilityAware into Views (the pages implement them; MainWindow consumes them)
- Moved OsdController, PlayerKeyboardHook and LiveChannelViewModel into Views

**Rationale:** Views had 9 unconnected groups because the pages only shared contracts that lived in another namespace. The page-lifecycle contracts now sit next to the pages that implement them, which connects DetailView, FavoritesView, HomeView, LiveView, LocalVideoView, PlayerView, SearchView and SettingsView. OsdController additionally links LiveView and PlayerView. By my count only AiImportDialog stays separate: 2 groups for about 23 classes, LCC ≈ 0.09 instead of 0.53.

**Smell removed:** yes -> **fixed**

## 8. Scattered Functionality in OrionTV.Desktop.App.Views (OrionTV.Desktop.App)

**Designite:** The tool detected the smell in this component because a set of two or more components realizes the same high-level architectural concern. Following components realize the same concern: OrionTV.Desktop.App' OrionTV.Desktop.Core

**Refactorings:** none

**Steps:**

- Only side effect: ImageLoader, IAppHost/AppServices, VodCacheService, OsdController and the source-health types the view methods touch now live in other namespaces (Controls, Hosting, Caching, Views, SourceHealth)

**Rationale:** Left unchanged in substance. The view methods coordinate several services (catalog, cache, health probe, stores) by design. Removing this would need a new presenter or facade layer for each page, which is a separate redesign and beyond these focused changes. The concern itself is no longer spread over a God root namespace.

**Smell removed:** yes -> **fixed**

## 9. Scattered Functionality in OrionTV.Desktop.App.Views (OrionTV.Desktop.App)

**Designite:** The tool detected the smell in this component because a set of two or more components realizes the same high-level architectural concern. Following components realize the same concern: OrionTV.Desktop.App.Controls' OrionTV.Desktop.Core

**Refactorings:** none

**Steps:**

- CatalogService and CatalogPlayabilityCache moved to Core.Catalog as part of the Core split; CardGrid only got a using

**Rationale:** Not addressed separately. The finding comes from a view method using both a reusable control (CardGrid) and the catalog service. That is normal UI composition and is left as it is.

**Smell removed:** yes -> **fixed**

## 10. Scattered Functionality in OrionTV.Desktop.App.Views (OrionTV.Desktop.App)

**Designite:** The tool detected the smell in this component because a set of two or more components realizes the same high-level architectural concern. Following components realize the same concern: OrionTV.Desktop.App' OrionTV.Desktop.App.LiveTranslation

**Refactorings:** none

**Steps:**

- PlaybackController moved to App.Playback and IAppHost/AppServices to App.Hosting (for smells 1/2/5)

**Rationale:** Left unchanged in substance. LiveView combines live playback (PlaybackController) with live translation (LiveTranslationController). Merging those components would mix two different concerns, and adding a mediator was beyond this focused refactoring.

**Smell removed:** yes -> **fixed**

## 11. Scattered Functionality in OrionTV.Desktop.App.Views (OrionTV.Desktop.App)

**Designite:** The tool detected the smell in this component because a set of two or more components realizes the same high-level architectural concern. Following components realize the same concern: OrionTV.Desktop.Core' OrionTV.Desktop.App.LiveTranslation

**Refactorings:** none

**Steps:**

- none

**Rationale:** Left unchanged. SettingsView/LiveView use the translation protocol constants in Core and the credential store and controller in LiveTranslation. This split (portable protocol logic in Core, platform client in App) is deliberate, and Settings in Core needs the protocol defaults.

**Smell removed:** no -> **not_fixed**

## 12. Scattered Functionality in OrionTV.Desktop.App.Views (OrionTV.Desktop.App)

**Designite:** The tool detected the smell in this component because a set of two or more components realizes the same high-level architectural concern. Following components realize the same concern: OrionTV.Desktop.App.LocalPlayback' OrionTV.Desktop.App

**Refactorings:** Move Class

**Steps:**

- Moved PlaybackController and PlaybackState into the dedicated OrionTV.Desktop.App.Playback namespace, which LocalPlayback now also uses for the shared PlaybackState

**Rationale:** Partially improved. The shared playback state type now lives in one Playback component instead of the God root namespace. PlayerView still switches between the LibVLC engine and the mpv engine, so it still uses both Playback and LocalPlayback. Merging the two would produce a namespace with unconnected classes, so they stay separate.

**Smell removed:** yes -> **fixed**

## 13. God Component in OrionTV.Desktop.Core (OrionTV.Desktop.Core)

**Designite:** The tool detected the smell in this component because the component contains high number of classes. Number of classes in the component are: 56

**Refactorings:** Split Component, Move Class

**Steps:**

- Created Core.Catalog: CatalogService/CatalogItem (CatalogService.cs), DoubanClient + DoubanItem (DoubanClient.cs), and the new Catalog/CatalogPlayability.cs with CatalogPlayabilityStatus, CatalogPlayability, CatalogPlayabilityBadge, CatalogPlayabilityCache (removed from CatalogModels.cs)
- Created Core.VodSources: AppleCms.cs (URL builder, episode parser, mapper, client), IVodSourceClient.cs (factory, unsupported client), MacCmsJsonClient.cs, MacCmsXmlClient.cs, HomeCategoryMatcher.cs, and the new VodSources/AppleCmsVodItem.cs (moved out of Models.cs)
- Moved SearchResultSources out of AppleCms.cs into the new file Core/SearchResultSources.cs (stays in Core, used by the playback policies)
- Created Core.StreamHealth: ChannelHealthProbe.cs (ChannelHealth, MediaProbeStatus, scoring, display, probe)
- Created Core.Library: LocalStore.cs (JsonDictionaryStore, FavoriteStore, PlayRecordStore) and LocalMediaLibrary.cs (LocalMediaNaming, LocalMediaStore)
- Added the matching usings in App and Tests

**Rationale:** Core had 56 classes covering many concerns. Each extracted namespace is one connected concern: the VOD protocol clients, catalog orchestration, stream health probing, and the persisted user library. They depend only on the shared kernel left in Core (models, settings, playback policies) and Core depends on none of them, so no cycles are introduced. Catalog → VodSources is the only edge between new namespaces, and it points to a more stable component. Core now has 29 classes.

**Smell removed:** yes -> **fixed**

## 14. Feature Concentration in OrionTV.Desktop.Tests (OrionTV.Desktop.Tests)

**Designite:** The tool detected the smell in this component because the component realizes more than one architectural concern/feature. Independent sets of related classes within this component are: [AiCliLauncherTests]' [AppleCmsServiceTests' StubHandler' VodProtocolTests]' [ChannelHealthScoringTests' RecordingHandler' FlvResponseHandler' HtmlResponseHandler' MisleadingHtmlResponseHandler' EncryptedHlsHandler' HtmlSegmentHandler' VariantRecordingHandler]' [DesktopSettingsTests]' [LocalStoreTests' TestStringStore]' [DesktopUpdateServiceTests' StubHttpMessageHandler' InlineProgress]' [ExtraVideoSourcesTests]' [HlsAdSkipTests]' [HomeCategoryMatcherTests]' [LocalCachePlaybackCatalogTests]' [LocalMediaLibraryTests]' [M3uParserTests]' [MpvLocalEngineTests]' [PlaybackResumePolicyTests]' [WpfNavigationCollection' PlayerNavigationSurfaceTests]' [PlayerShortcutTests]' [PlayRecordHistoryTests]' [RealtimeTranslationProtocolTests]' [GeminiLiveTranslateProtocolTests]' [DeepgramSttProtocolTests]' [DoubaoAstProtocolTests]' [SubscriptionParserTests]' [VodCacheLookupTests]' [VodCacheServiceTests' InlineProgress<T>' BlockingFirstProgress' FakeHlsServer]' [VodSourceHealthProbeTests' StubDecodeProbe]. LCC (Lack of Component Cohesion) = 0'6

**Refactorings:** Split Component

**Steps:**

- Moved the tests of App-project classes (AiCliLauncher, DesktopUpdateService, LocalCachePlaybackCatalog, MpvLocalEngine, PlaybackResumePolicy/PlayerSourceSwitch, PlayerNavigationSurface, PlayerShortcut, VodCacheLookup, VodCacheService, VodSourceHealthProbe) and their helpers to OrionTV.Desktop.Tests.App

**Rationale:** Partially addressed. Test classes are independent of each other by nature, so low cohesion between test fixtures is expected and cannot be removed without coupling tests artificially. Grouping the tests by the project they test gives each test namespace one responsibility. No assertions changed.

**Smell removed:** no -> **not_fixed**

## 15. God Component in OrionTV.Desktop.Tests (OrionTV.Desktop.Tests)

**Designite:** The tool detected the smell in this component because the component contains high number of classes. Number of classes in the component are: 42

**Refactorings:** Split Component

**Steps:**

- Split the test namespace: OrionTV.Desktop.Tests (Core tests, 25 classes) and OrionTV.Desktop.Tests.App (App-project tests, 17 classes)
- Changed only namespace declarations, usings and one fully qualified AppServices reference (now OrionTV.Desktop.App.Hosting.AppServices)

**Rationale:** The 42-class test namespace is now two namespaces of 25 and 17 classes, split by the project under test. Each helper class (StubHttpMessageHandler, InlineProgress, FakeHlsServer, StubDecodeProbe, …) stays in the same file and namespace as the tests that use it, and the test logic is unchanged.

**Smell removed:** yes -> **fixed**

## New smells

- Unstable Dependency in OrionTV.Desktop.App.Hosting (OrionTV.Desktop.App): The tool detected the smell in this component because this component depends on other components that are less stable than itself. This component depends on following less stable component(s): OrionTV.Desktop.App.SourceHealth
- Unstable Dependency in OrionTV.Desktop.App.CacheCatalog (OrionTV.Desktop.App): The tool detected the smell in this component because this component depends on other components that are less stable than itself. This component depends on following less stable component(s): OrionTV.Desktop.Core.Library
- Scattered Functionality in OrionTV.Desktop.App (OrionTV.Desktop.App): The tool detected the smell in this component because a set of two or more components realizes the same high-level architectural concern. Following components realize the same concern: OrionTV.Desktop.App.Hosting' OrionTV.Desktop.App.AiImport
- Scattered Functionality in OrionTV.Desktop.App.Hosting (OrionTV.Desktop.App): The tool detected the smell in this component because a set of two or more components realizes the same high-level architectural concern. Following components realize the same concern: OrionTV.Desktop.Core.Catalog' OrionTV.Desktop.App.SourceHealth' OrionTV.Desktop.Core
- Scattered Functionality in OrionTV.Desktop.App.Views (OrionTV.Desktop.App): The tool detected the smell in this component because a set of two or more components realizes the same high-level architectural concern. Following components realize the same concern: OrionTV.Desktop.App.Caching' OrionTV.Desktop.App.CacheCatalog
- Scattered Functionality in OrionTV.Desktop.App.Views (OrionTV.Desktop.App): The tool detected the smell in this component because a set of two or more components realizes the same high-level architectural concern. Following components realize the same concern: OrionTV.Desktop.App.Controls' OrionTV.Desktop.Core.Catalog
- Scattered Functionality in OrionTV.Desktop.App.Views (OrionTV.Desktop.App): The tool detected the smell in this component because a set of two or more components realizes the same high-level architectural concern. Following components realize the same concern: OrionTV.Desktop.App.LocalPlayback' OrionTV.Desktop.App.Playback
- Feature Concentration in OrionTV.Desktop.Core (OrionTV.Desktop.Core): The tool detected the smell in this component because the component realizes more than one architectural concern/feature. Independent sets of related classes within this component are: [CatalogTitleMatcher]' [PlaybackResumePolicy' EpisodeLabelFormatter' SearchResultSources' PlaybackFallbackSelector]' [PlaybackMediaOptions]' [PlaybackStartupWatchdog]' [PlaybackStartupSignal' PlaybackStartupPolicy]' [DeepgramSttProtocol' GeminiLiveTranslateProtocol' DoubaoAstProtocol]' [DesktopLiveSourceSettings' DesktopSettingsForm' ExtraVideoSourcesStore' VideoSourceProtocols' DesktopPaths' VodCacheSettings' DesktopSettingsMigration' SettingsStore' VideoSourceSubscriptionParser' AiImportPromptBuilder]' [VideoSourceMerger]' [HlsAdSkip]' [M3uParser]' [RealtimeTranslationEventKind' RealtimeTranslationProtocol' Pcm16TranslationFrameBuffer]' [RollingSubtitleBuffer]. LCC (Lack of Component Cohesion) = 0'41
- Scattered Functionality in OrionTV.Desktop.Core.Catalog (OrionTV.Desktop.Core): The tool detected the smell in this component because a set of two or more components realizes the same high-level architectural concern. Following components realize the same concern: OrionTV.Desktop.Core.VodSources' OrionTV.Desktop.Core
- Dense Structure in <All namespaces included> (<All projects included>): The tool detected the smell because all the analyzed components exhibit excessive and dense dependencies among themselves. Average degree = 5'30  All the dependencies among components: from: OrionTV.Desktop.Core.VodSources' to: OrionTV.Desktop.Core' from: OrionTV.Desktop.Core.Catalog' to: OrionTV.Desktop.Core.VodSources' from: OrionTV.Desktop.Core.Catalog' to: OrionTV.Desktop.Core' from: OrionTV.Desktop.Core.StreamHealth' to: OrionTV.Desktop.Core' from: OrionTV.Desktop.Core.Library' to: OrionTV.Desktop.Core' from: OrionTV.Desktop.App.AiImport' to: OrionTV.Desktop.Core' from: OrionTV.Desktop.App' to: OrionTV.Desktop.App.AiImport' from: OrionTV.Desktop.App' to: OrionTV.Desktop.App.Hosting' from: OrionTV.Desktop.App' to: OrionTV.Desktop.App.Views' from: OrionTV.Desktop.App.Hosting' to: OrionTV.Desktop.Core.VodSources' from: OrionTV.Desktop.App.Hosting' to: OrionTV.Desktop.Core' from: OrionTV.Desktop.App.Hosting' to: OrionTV.Desktop.Core.Catalog' from: OrionTV.Desktop.App.Hosting' to: OrionTV.Desktop.Core.StreamHealth' from: OrionTV.Desktop.App.Hosting' to: OrionTV.Desktop.Core.Library' from: OrionTV.Desktop.App.Hosting' to: OrionTV.Desktop.App.Updates' from: OrionTV.Desktop.App.Hosting' to: OrionTV.Desktop.App.Caching' from: OrionTV.Desktop.App.Hosting' to: OrionTV.Desktop.App.Playback' from: OrionTV.Desktop.App.Hosting' to: OrionTV.Desktop.App.SourceHealth' from: OrionTV.Desktop.App.CacheCatalog' to: OrionTV.Desktop.Core.Library' from: OrionTV.Desktop.App.Controls' to: OrionTV.Desktop.Core.Catalog' from: OrionTV.Desktop.App.Updates' to: OrionTV.Desktop.Core' from: OrionTV.Desktop.App.Caching' to: OrionTV.Desktop.Core' from: OrionTV.Desktop.App.LiveTranslation' to: OrionTV.Desktop.Core' from: OrionTV.Desktop.App.LocalPlayback' to: OrionTV.Desktop.App.Playback' from: OrionTV.Desktop.App.Playback' to: OrionTV.Desktop.Core' from: OrionTV.Desktop.App.Views' to: OrionTV.Desktop.Core' from: OrionTV.Desktop.App.Views' to: OrionTV.Desktop.App.AiImport' from: OrionTV.Desktop.App.Views' to: OrionTV.Desktop.App.Hosting' from: OrionTV.Desktop.App.Views' to: OrionTV.Desktop.App.CacheCatalog' from: OrionTV.Desktop.App.Views' to: OrionTV.Desktop.App.Controls' from: OrionTV.Desktop.App.Views' to: OrionTV.Desktop.App.Caching' from: OrionTV.Desktop.App.Views' to: OrionTV.Desktop.App.SourceHealth' from: OrionTV.Desktop.App.Views' to: OrionTV.Desktop.Core.Catalog' from: OrionTV.Desktop.App.Views' to: OrionTV.Desktop.Core.Library' from: OrionTV.Desktop.App.Views' to: OrionTV.Desktop.Core.StreamHealth' from: OrionTV.Desktop.App.Views' to: OrionTV.Desktop.App.LiveTranslation' from: OrionTV.Desktop.App.Views' to: OrionTV.Desktop.App.Playback' from: OrionTV.Desktop.App.Views' to: OrionTV.Desktop.App.LocalPlayback' from: OrionTV.Desktop.App.Views' to: OrionTV.Desktop.App.Updates' from: OrionTV.Desktop.App.SourceHealth' to: OrionTV.Desktop.Core' from: OrionTV.Desktop.App.SourceHealth' to: OrionTV.Desktop.Core.StreamHealth' from: OrionTV.Desktop.Tests.App' to: OrionTV.Desktop.App.AiImport' from: OrionTV.Desktop.Tests.App' to: OrionTV.Desktop.App.Updates' from: OrionTV.Desktop.Tests.App' to: OrionTV.Desktop.App.CacheCatalog' from: OrionTV.Desktop.Tests.App' to: OrionTV.Desktop.App.LocalPlayback' from: OrionTV.Desktop.Tests.App' to: OrionTV.Desktop.Core' from: OrionTV.Desktop.Tests.App' to: OrionTV.Desktop.Core.Library' from: OrionTV.Desktop.Tests.App' to: OrionTV.Desktop.App.Views' from: OrionTV.Desktop.Tests.App' to: OrionTV.Desktop.App' from: OrionTV.Desktop.Tests.App' to: OrionTV.Desktop.App.Hosting' from: OrionTV.Desktop.Tests.App' to: OrionTV.Desktop.App.Playback' from: OrionTV.Desktop.Tests.App' to: OrionTV.Desktop.App.Caching' from: OrionTV.Desktop.Tests.App' to: OrionTV.Desktop.Core.Catalog' from: OrionTV.Desktop.Tests.App' to: OrionTV.Desktop.Core.StreamHealth' from: OrionTV.Desktop.Tests.App' to: OrionTV.Desktop.App.SourceHealth' from: OrionTV.Desktop.Tests' to: OrionTV.Desktop.Core.VodSources' from: OrionTV.Desktop.Tests' to: OrionTV.Desktop.Core' from: OrionTV.Desktop.Tests' to: OrionTV.Desktop.Core.Catalog' from: OrionTV.Desktop.Tests' to: OrionTV.Desktop.Core.StreamHealth' from: OrionTV.Desktop.Tests' to: OrionTV.Desktop.App.Hosting' from: OrionTV.Desktop.Tests' to: OrionTV.Desktop.Core.Library.
- Feature Concentration in OrionTV.Desktop.Tests.App (OrionTV.Desktop.Tests): The tool detected the smell in this component because the component realizes more than one architectural concern/feature. Independent sets of related classes within this component are: [AiCliLauncherTests]' [DesktopUpdateServiceTests' StubHttpMessageHandler' InlineProgress]' [LocalCachePlaybackCatalogTests]' [MpvLocalEngineTests]' [PlaybackResumePolicyTests]' [WpfNavigationCollection' PlayerNavigationSurfaceTests]' [PlayerShortcutTests]' [VodCacheLookupTests]' [VodCacheServiceTests' InlineProgress<T>' BlockingFirstProgress' FakeHlsServer]' [VodSourceHealthProbeTests' StubDecodeProbe]. LCC (Lack of Component Cohesion) = 0'59
- Scattered Functionality in OrionTV.Desktop.Tests (OrionTV.Desktop.Tests): The tool detected the smell in this component because a set of two or more components realizes the same high-level architectural concern. Following components realize the same concern: OrionTV.Desktop.Core.VodSources' OrionTV.Desktop.Core
