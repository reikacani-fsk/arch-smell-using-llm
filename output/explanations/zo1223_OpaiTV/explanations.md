# How the architectural smells of zo1223/OpaiTV emerged

## 1. Cyclic Dependency in OrionTV.Desktop.App (OrionTV.Desktop.App)

**Designite:** The tool detected the smell in this component because this component participates in a cyclic dependency. The participating components in the cycle are: OrionTV.Desktop.App' OrionTV.Desktop.App.Views

**Classes:** OrionTV.Desktop.App.AiCliLauncher; OrionTV.Desktop.App.MainWindow; OrionTV.Desktop.App.Views.AiImportDialog; OrionTV.Desktop.App.Views.LiveView; OrionTV.Desktop.App.Views.PlayerView

**Commits that changed its files:** 9

**Emerged in:** b3ae88d60f 2026-07-22

**How:** The cycle was already present in the first commit that touched these files, the initial import b3ae88d60f. In that commit, MainWindow (namespace OrionTV.Desktop.App) imports OrionTV.Desktop.App.Views and builds every page in CreateView (HomeView, LiveView, PlayerView, …). It also opens AiImportDialog from OpenAiImport. In the other direction, AiImportDialog takes an IAppHost and an AiCliTool and calls AiCliLauncher.ResolveDocsDirectory/Launch/LaunchDiscovery. LiveView and PlayerView take IAppHost and use PlaybackController, OsdController and AppServices, all from the App namespace. So App → Views → App existed from the start. Commit f1bbae77f7 tightened the loop: MainWindow gained a persistent PlayerView field and player-specific navigation (NavigateToPlayer, ClosePlayer, TryNavigateFromPlayerToDetail), and PlayerView started using PlayerKeyboardHook from App. Commit e137971afc added the App-level INavigationVisibilityAware interface, which LiveView now implements, while MainWindow's new section navigation calls back into the views.

**Timeline:**

- `b3ae88d60f`: MainWindow creates all Views and AiImportDialog; AiImportDialog uses AiCliLauncher/AiCliTool/IAppHost; LiveView and PlayerView use IAppHost, PlaybackController and OsdController, closing the App ↔ Views cycle.
- `f1bbae77f7`: MainWindow keeps a resident PlayerView with dedicated navigation logic; PlayerView uses App's PlayerKeyboardHook, adding edges in both directions.
- `e137971afc`: LiveView implements the new App interface INavigationVisibilityAware; MainWindow's section state management depends more deeply on concrete views.

**Why it is a problem:** The navigation shell (MainWindow, IAppHost) and the pages it hosts know each other's concrete types. The views cannot be compiled, tested or reused without the shell, and the shell cannot change without touching specific views such as PlayerView. Every new page or navigation feature, such as the resident player or visibility callbacks, makes the two namespaces harder to separate.

## 2. Cyclic Dependency in OrionTV.Desktop.App (OrionTV.Desktop.App)

**Designite:** The tool detected the smell in this component because this component participates in a cyclic dependency. The participating components in the cycle are: OrionTV.Desktop.App' OrionTV.Desktop.App.Views' OrionTV.Desktop.App.LocalPlayback

**Classes:** OrionTV.Desktop.App.AiCliLauncher; OrionTV.Desktop.App.MainWindow; OrionTV.Desktop.App.Views.AiImportDialog; OrionTV.Desktop.App.Views.LiveView; OrionTV.Desktop.App.Views.PlayerView; OrionTV.Desktop.App.LocalPlayback.MpvLocalEngine

**Commits that changed its files:** 9

**Emerged in:** b3ae88d60f 2026-07-22

**How:** The three-component cycle was already present in the initial import b3ae88d60f. MainWindow (App) creates PlayerView (Views). PlayerView imports OrionTV.Desktop.App.LocalPlayback and holds an MpvLocalEngine. MpvLocalEngine (LocalPlayback) stores and raises the PlaybackState enum, which is declared in App's PlaybackController.cs. That closes App → Views → LocalPlayback → App. Later commits deepened the coupling. e1991e7308 added a FullscreenChanged event that PlayerView handles, and PlayerView now drives the engine's fullscreen and seeking. f1bbae77f7 made MpvLocalEngine set PlaybackState from file-loaded/end-file events and added VideoOutputChanged. In the same commit MainWindow kept PlayerView resident, and AiCliLauncher-related navigation stayed in MainWindow.

**Timeline:**

- `b3ae88d60f`: PlayerView uses MpvLocalEngine; MpvLocalEngine depends on App.PlaybackState; MainWindow creates PlayerView, forming the cycle.
- `e1991e7308`: MpvLocalEngine gains FullscreenChanged/SetFullscreen, which PlayerView wires up, deepening the Views ↔ LocalPlayback link.
- `f1bbae77f7`: MpvLocalEngine sets App.PlaybackState from more mpv events and adds VideoOutputChanged; MainWindow holds a persistent PlayerView.

**Why it is a problem:** The mpv engine is meant to be a self-contained local playback backend, yet it depends on a state enum defined next to the LibVLC PlaybackController in the root App namespace. As a result, LocalPlayback cannot be extracted or tested without pulling in the whole App and Views layers. Any change to PlaybackState ripples through the mpv engine, the player view and the shell.

## 3. Feature Concentration in OrionTV.Desktop.App (OrionTV.Desktop.App)

**Designite:** The tool detected the smell in this component because the component realizes more than one architectural concern/feature. Independent sets of related classes within this component are: [AiCliTool' AiCliLauncher' AiCliTaskMode' MainWindow' SectionNavigationState' AppPage' IAppHost' INavigationAware' INavigationVisibilityAware' AiSourceWatcher' ChangeKind' AppServices' DesktopUpdateService' PlaybackController' VodCacheService' InlineProgress<T>' VodCacheLog' VodDownloadManager' Job' VodPlayableSourceResolver' VodSourceProbeStatus' VodSourceHealthDisplay' VodSourceHealthProbe' LibVlcMediaDecodeProbe' WindowMessage' HlsAesDecryptMerger' VodCacheSession' CacheFile' PlaybackState' VodDownloadJobStatus' MediaDecodeProbeStatus' IMediaDecodeProbe' VodSourceProbeSampler]' [App]' [EmptyStringToVisibilityConverter]' [ImageLoader]' [LiveChannelViewModel]' [LocalCachePlaybackCatalog]' [OsdController]' [PlayerKeyboardHook' KbdLlHookStruct]' [VodCacheLookup]. LCC (Lack of Component Cohesion) = 0'21

**Classes:** OrionTV.Desktop.App.AiCliTool; OrionTV.Desktop.App.AiCliLauncher; OrionTV.Desktop.App.AiCliTaskMode; OrionTV.Desktop.App.AiSourceWatcher; OrionTV.Desktop.App.ChangeKind; OrionTV.Desktop.App.App; OrionTV.Desktop.App.AppServices; OrionTV.Desktop.App.DesktopUpdateService; OrionTV.Desktop.App.EmptyStringToVisibilityConverter; OrionTV.Desktop.App.HlsAesDecryptMerger; OrionTV.Desktop.App.ImageLoader; OrionTV.Desktop.App.LiveChannelViewModel; OrionTV.Desktop.App.LocalCachePlaybackCatalog; OrionTV.Desktop.App.MainWindow; OrionTV.Desktop.App.SectionNavigationState; OrionTV.Desktop.App.AppPage; OrionTV.Desktop.App.IAppHost; OrionTV.Desktop.App.INavigationAware; OrionTV.Desktop.App.INavigationVisibilityAware; OrionTV.Desktop.App.OsdController; OrionTV.Desktop.App.PlaybackState; OrionTV.Desktop.App.PlaybackController; OrionTV.Desktop.App.PlayerKeyboardHook; OrionTV.Desktop.App.KbdLlHookStruct; OrionTV.Desktop.App.VodCacheLookup; OrionTV.Desktop.App.VodCacheSession; OrionTV.Desktop.App.CacheFile; OrionTV.Desktop.App.VodCacheService; OrionTV.Desktop.App.InlineProgress<T>; OrionTV.Desktop.App.VodCacheLog; OrionTV.Desktop.App.VodDownloadJobStatus; OrionTV.Desktop.App.VodDownloadManager; OrionTV.Desktop.App.Job; OrionTV.Desktop.App.VodPlayableSourceResolver; OrionTV.Desktop.App.VodSourceProbeStatus; OrionTV.Desktop.App.MediaDecodeProbeStatus; OrionTV.Desktop.App.IMediaDecodeProbe; OrionTV.Desktop.App.VodSourceProbeSampler; OrionTV.Desktop.App.VodSourceHealthDisplay; OrionTV.Desktop.App.VodSourceHealthProbe; OrionTV.Desktop.App.LibVlcMediaDecodeProbe; OrionTV.Desktop.App.WindowMessage

**Commits that changed its files:** 8

**Emerged in:** b3ae88d60f 2026-07-22

**How:** The initial import b3ae88d60f already placed several unrelated concerns in the flat root namespace OrionTV.Desktop.App: AI CLI launching (AiCliLauncher, AiSourceWatcher), the navigation shell (MainWindow, Navigation.cs types), LibVLC playback (PlaybackController), HLS caching/downloading/decryption (VodCacheService, VodDownloadManager, HlsAesDecryptMerger), and UI helpers that use none of these (App, EmptyStringToVisibilityConverter, ImageLoader, LiveChannelViewModel, OsdController). That already gives independent class groups. Later commits widened the spread. fe42a7f077 taught ImageLoader to load local files. f1bbae77f7 added an update service (DesktopUpdateService), a low-level keyboard hook (PlayerKeyboardHook, KbdLlHookStruct, an isolated group), a cache index (VodCacheLookup, another isolated group), and source health probing and resolution (VodSourceHealthProbe and related types, VodPlayableSourceResolver). e137971afc added LocalCachePlaybackCatalog (isolated), SectionNavigationState, INavigationVisibilityAware and InlineProgress<T>.

**Timeline:**

- `b3ae88d60f`: Root namespace contains AI tooling, the navigation shell, playback, VOD caching and download, plus independent helpers (App, converter, ImageLoader, LiveChannelViewModel, OsdController).
- `fe42a7f077`: ImageLoader gains local file loading for the local media library, still separate from the other groups.
- `f1bbae77f7`: Adds DesktopUpdateService, PlayerKeyboardHook/KbdLlHookStruct, VodCacheLookup, VodPlayableSourceResolver and the VodSourceHealthProbe family to the same namespace.
- `e137971afc`: Adds LocalCachePlaybackCatalog as another independent group, plus SectionNavigationState, INavigationVisibilityAware and InlineProgress<T>.

**Why it is a problem:** Application updates, AI source discovery, HLS AES decryption, keyboard hooking and WPF value converters all live in one namespace with an LCC of 0.21. Unrelated features change the same component in every release commit (e.g. f1bbae77f7, e137971afc). There is no boundary showing which classes form the caching subsystem versus the shell versus the playback engine.

## 4. God Component in OrionTV.Desktop.App (OrionTV.Desktop.App)

**Designite:** The tool detected the smell in this component because the component contains high number of classes. Number of classes in the component are: 42

**Classes:** OrionTV.Desktop.App.AiCliTool; OrionTV.Desktop.App.AiCliLauncher; OrionTV.Desktop.App.AiCliTaskMode; OrionTV.Desktop.App.AiSourceWatcher; OrionTV.Desktop.App.ChangeKind; OrionTV.Desktop.App.App; OrionTV.Desktop.App.AppServices; OrionTV.Desktop.App.DesktopUpdateService; OrionTV.Desktop.App.EmptyStringToVisibilityConverter; OrionTV.Desktop.App.HlsAesDecryptMerger; OrionTV.Desktop.App.ImageLoader; OrionTV.Desktop.App.LiveChannelViewModel; OrionTV.Desktop.App.LocalCachePlaybackCatalog; OrionTV.Desktop.App.MainWindow; OrionTV.Desktop.App.SectionNavigationState; OrionTV.Desktop.App.AppPage; OrionTV.Desktop.App.IAppHost; OrionTV.Desktop.App.INavigationAware; OrionTV.Desktop.App.INavigationVisibilityAware; OrionTV.Desktop.App.OsdController; OrionTV.Desktop.App.PlaybackState; OrionTV.Desktop.App.PlaybackController; OrionTV.Desktop.App.PlayerKeyboardHook; OrionTV.Desktop.App.KbdLlHookStruct; OrionTV.Desktop.App.VodCacheLookup; OrionTV.Desktop.App.VodCacheSession; OrionTV.Desktop.App.CacheFile; OrionTV.Desktop.App.VodCacheService; OrionTV.Desktop.App.InlineProgress<T>; OrionTV.Desktop.App.VodCacheLog; OrionTV.Desktop.App.VodDownloadJobStatus; OrionTV.Desktop.App.VodDownloadManager; OrionTV.Desktop.App.Job; OrionTV.Desktop.App.VodPlayableSourceResolver; OrionTV.Desktop.App.VodSourceProbeStatus; OrionTV.Desktop.App.MediaDecodeProbeStatus; OrionTV.Desktop.App.IMediaDecodeProbe; OrionTV.Desktop.App.VodSourceProbeSampler; OrionTV.Desktop.App.VodSourceHealthDisplay; OrionTV.Desktop.App.VodSourceHealthProbe; OrionTV.Desktop.App.LibVlcMediaDecodeProbe; OrionTV.Desktop.App.WindowMessage

**Commits that changed its files:** 8

**Emerged in:** f1bbae77f7 2026-07-27

**How:** The initial import b3ae88d60f already placed about 25 classes in OrionTV.Desktop.App. These were the AI CLI types, AiSourceWatcher/ChangeKind, App, AppServices, the converter, HlsAesDecryptMerger, ImageLoader, LiveChannelViewModel, MainWindow, the navigation types, OsdController, PlaybackState/PlaybackController, the VodCache* types, and VodDownloadManager/Job/VodDownloadJobStatus. That is large but below the class-count threshold. Release commit f1bbae77f7 pushed it over in one step by adding DesktopUpdateService, PlayerKeyboardHook and KbdLlHookStruct, VodCacheLookup, VodPlayableSourceResolver, and the whole VodSourceHealthProbe.cs family (VodSourceProbeStatus, MediaDecodeProbeStatus, IMediaDecodeProbe, VodSourceProbeSampler, VodSourceHealthDisplay, VodSourceHealthProbe, LibVlcMediaDecodeProbe, and presumably WindowMessage). That brought it to roughly 38 classes. e137971afc then added LocalCachePlaybackCatalog, SectionNavigationState, INavigationVisibilityAware and InlineProgress<T>, reaching the reported 42.

**Timeline:**

- `b3ae88d60f`: About 25 classes imported into the root App namespace.
- `f1bbae77f7`: Adds about 13 classes (update service, keyboard hook, cache lookup, playable source resolver, source health probe family), crossing the God Component threshold.
- `e137971afc`: Adds LocalCachePlaybackCatalog, SectionNavigationState, INavigationVisibilityAware and InlineProgress<T>, reaching 42 classes.

**Why it is a problem:** Each feature release drops its new services straight into the root namespace instead of sub-namespaces like LocalPlayback or LiveTranslation. The component now mixes a 2,000+ line VodCacheService with updater, hook and probe code. Developers must understand the whole namespace to change any part, and nothing can be reused or tested in isolation.

## 5. Unstable Dependency in OrionTV.Desktop.App (OrionTV.Desktop.App)

**Designite:** The tool detected the smell in this component because this component depends on other components that are less stable than itself. This component depends on following less stable component(s): OrionTV.Desktop.App.Views

**Classes:** OrionTV.Desktop.App.AiImportDialog; OrionTV.Desktop.App.DetailView; OrionTV.Desktop.App.FavoritesView; OrionTV.Desktop.App.HomeView; OrionTV.Desktop.App.LiveView; OrionTV.Desktop.App.LocalVideoView; OrionTV.Desktop.App.PlayerView; OrionTV.Desktop.App.SearchView; OrionTV.Desktop.App.SettingsView

**Commits that changed its files:** 8

**Emerged in:** b3ae88d60f 2026-07-22

**How:** The dependency was established in the initial import b3ae88d60f. MainWindow in the App component directly instantiates every view in OrionTV.Desktop.App.Views (HomeView, SearchView, FavoritesView, LiveView, LocalVideoView, SettingsView, DetailView, PlayerView) and AiImportDialog. The Views component has many outgoing dependencies (App, Core, LiveTranslation, LocalPlayback, Controls) and few incoming ones, so it is less stable than App, which is used by Views, LocalPlayback and the others. Later commits kept the views volatile and growing: fe42a7f077 added the local media library in LocalVideoView, HomeView and PlayerView. f1bbae77f7 rewrote large parts of DetailView, HomeView and PlayerView and added PlayerView helper types. e137971afc added batch decryption and visibility-aware playback in DetailView, LiveView and LocalVideoView, while MainWindow became even more coupled to concrete views.

**Timeline:**

- `b3ae88d60f`: MainWindow (App) instantiates all concrete Views; Views depends on many components, making it less stable than App.
- `fe42a7f077`: Views extended for local media playback (more Core and App dependencies), increasing their instability.
- `f1bbae77f7`: Heavy changes to DetailView, HomeView, PlayerView, SearchView and SettingsView; MainWindow adds PlayerView-specific navigation.
- `e137971afc`: DetailView, LiveView and LocalVideoView change again; MainWindow's section navigation depends on concrete DetailView and PlayerView.

**Why it is a problem:** The core App component, which hosts shared services and the IAppHost contract, depends on the most frequently rewritten code in the project, the page code-behind files. Every release changes PlayerView, DetailView and others, so MainWindow and the stable services it carries are exposed to that churn. The cleaner direction would be for views to depend on App, not the reverse.

## 6. Unstable Dependency in OrionTV.Desktop.App.LocalPlayback (OrionTV.Desktop.App)

**Designite:** The tool detected the smell in this component because this component depends on other components that are less stable than itself. This component depends on following less stable component(s): OrionTV.Desktop.App

**Classes:** OrionTV.Desktop.App.LocalPlayback.PlaybackState

**Commits that changed its files:** 2

**Emerged in:** b3ae88d60f 2026-07-22

**How:** This was already present in the initial import b3ae88d60f. MpvLocalEngine in OrionTV.Desktop.App.LocalPlayback stores its state as PlaybackState, which is declared in desktop/OrionTV.Desktop.App/PlaybackController.cs in the root App namespace, so LocalPlayback depends on App. App has many outgoing dependencies, including Views, Core and LibVLC-based classes, and is therefore less stable than the small LocalPlayback component. f1bbae77f7 modified PlaybackController.cs (Vout handling, volume/mute state, pending-seek retries). MpvLocalEngine kept depending on the same file for PlaybackState and used it in more places (file-loaded, end-file, error).

**Timeline:**

- `b3ae88d60f`: MpvLocalEngine uses App.PlaybackState, defined alongside PlaybackController in the less stable App component.
- `f1bbae77f7`: PlaybackController.cs is extended while MpvLocalEngine relies on PlaybackState in more event handlers, keeping the dependency alive.

**Why it is a problem:** A small, focused playback engine depends on a shared enum that sits in the volatile root namespace inside the LibVLC controller's file. Any edit to PlaybackController.cs or the App namespace can affect the mpv engine. The enum belongs in a stable shared location, such as Core or a playback abstraction.

## 7. Feature Concentration in OrionTV.Desktop.App.Views (OrionTV.Desktop.App)

**Designite:** The tool detected the smell in this component because the component realizes more than one architectural concern/feature. Independent sets of related classes within this component are: [AiImportDialog]' [DetailView]' [FavoritesView]' [HomeView]' [LiveView]' [LocalVideoView' ActiveJobItem' LocalCacheItem' LocalMediaCardItem]' [PlayerShortcutCommand' PlayerShortcutMap' PlayerView' LoadingNoticeMode' PlayerSourceSwitchPolicy' PlayerEpisodeAdvancePolicy]' [SearchView]' [SettingsView]. LCC (Lack of Component Cohesion) = 0'53

**Classes:** OrionTV.Desktop.App.Views.AiImportDialog; OrionTV.Desktop.App.Views.DetailView; OrionTV.Desktop.App.Views.FavoritesView; OrionTV.Desktop.App.Views.HomeView; OrionTV.Desktop.App.Views.LiveView; OrionTV.Desktop.App.Views.LocalVideoView; OrionTV.Desktop.App.Views.ActiveJobItem; OrionTV.Desktop.App.Views.LocalCacheItem; OrionTV.Desktop.App.Views.LocalMediaCardItem; OrionTV.Desktop.App.Views.PlayerShortcutCommand; OrionTV.Desktop.App.Views.PlayerShortcutMap; OrionTV.Desktop.App.Views.PlayerSourceSwitchPolicy; OrionTV.Desktop.App.Views.PlayerEpisodeAdvancePolicy; OrionTV.Desktop.App.Views.PlayerView; OrionTV.Desktop.App.Views.LoadingNoticeMode; OrionTV.Desktop.App.Views.SearchView; OrionTV.Desktop.App.Views.SettingsView

**Commits that changed its files:** 8

**Emerged in:** b3ae88d60f 2026-07-22

**How:** The initial import b3ae88d60f already put nine independent page classes into OrionTV.Desktop.App.Views: AiImportDialog, DetailView, FavoritesView, HomeView, LiveView, LocalVideoView with its ActiveJobItem/LocalCacheItem, PlayerView with LoadingNoticeMode, SearchView and SettingsView. None of them use each other; they only share IAppHost. So the component realized multiple unrelated features from the start. fe42a7f077 added LocalMediaCardItem to LocalVideoView for the local media library. f1bbae77f7 added PlayerShortcutCommand, PlayerShortcutMap, PlayerSourceSwitchPolicy and PlayerEpisodeAdvancePolicy inside PlayerView.xaml.cs, along with update UI in SettingsView. e137971afc added batch decryption to DetailView and LocalVideoView.

**Timeline:**

- `b3ae88d60f`: Nine mutually independent pages (AI import, detail, favorites, home, live, local video, player, search, settings) placed in one namespace.
- `fe42a7f077`: LocalMediaCardItem added for the local media library within LocalVideoView.
- `f1bbae77f7`: Player shortcut and source-switch/episode-advance policy types added inside PlayerView.xaml.cs; SettingsView gains app update UI.
- `e137971afc`: DetailView and LocalVideoView gain batch decrypt-merge features, further growing unrelated concerns.

**Why it is a problem:** Views mixes live TV with translation, VOD playback, AI source import, app updates and local media management, and these groups share nothing but IAppHost (LCC 0.53). Player policy logic is embedded in a code-behind file, and each feature lives in its own huge page class. Changes to unrelated features all land in this one namespace.

## 8. Scattered Functionality in OrionTV.Desktop.App.Views (OrionTV.Desktop.App)

**Designite:** The tool detected the smell in this component because a set of two or more components realizes the same high-level architectural concern. Following components realize the same concern: OrionTV.Desktop.App' OrionTV.Desktop.Core

**Classes:** OrionTV.Desktop.App.ImageLoader; OrionTV.Desktop.Core.FavoriteStore; OrionTV.Desktop.App.AppServices; OrionTV.Desktop.Core.IVodSourceClient; OrionTV.Desktop.Core.VodSourceClientFactory; OrionTV.Desktop.Core.PlayRecordStore; OrionTV.Desktop.Core.PlaybackResumePolicy; OrionTV.Desktop.App.IAppHost; OrionTV.Desktop.Core.LocalMediaStore; OrionTV.Desktop.App.LocalCachePlaybackCatalog; OrionTV.Desktop.App.VodCacheService; OrionTV.Desktop.Core.LocalMediaNaming; OrionTV.Desktop.Core.EpisodeLabelFormatter; OrionTV.Desktop.App.OsdController; OrionTV.Desktop.Core.DesktopLiveSourceSettings; OrionTV.Desktop.Core.M3uParser; OrionTV.Desktop.App.VodDownloadManager; OrionTV.Desktop.Core.CatalogService; OrionTV.Desktop.Core.SearchResultSources; OrionTV.Desktop.App.VodSourceHealthProbe; OrionTV.Desktop.App.VodSourceHealthDisplay

**Commits that changed its files:** 7

**Emerged in:** b3ae88d60f 2026-07-22

**How:** Since the initial import b3ae88d60f, the media-catalog and library concern has been split between OrionTV.Desktop.Core and OrionTV.Desktop.App. AppServices wires Core's VodSourceClientFactory, CatalogService, M3uParser, FavoriteStore and PlayRecordStore together with App's own VodCacheService and VodDownloadManager. IAppHost exposes this to views, and ImageLoader and OsdController live in App. fe42a7f077 added Core's LocalMediaStore to AppServices and taught ImageLoader and VodCacheService about local posters. f1bbae77f7 put Core's PlaybackResumePolicy logic into Navigation.cs (PlaybackResumeContext) and added VodSourceHealthProbe and VodSourceHealthDisplay in App, which use Core's EpisodeLabelFormatter and ChannelHealthProbe. e137971afc added LocalCachePlaybackCatalog in App, which reimplements grouping with Core's LocalMediaNaming and SearchResult.

**Timeline:**

- `b3ae88d60f`: AppServices/IAppHost combine Core catalog/store classes with App-side VodCacheService/VodDownloadManager; ImageLoader and OsdController live in App.
- `fe42a7f077`: LocalMediaStore (Core) added to AppServices; ImageLoader and VodCacheService extended for local media and posters.
- `f1bbae77f7`: Navigation.cs wraps Core's PlaybackResumePolicy; App adds VodSourceHealthProbe/VodSourceHealthDisplay built on Core helpers.
- `e137971afc`: App adds LocalCachePlaybackCatalog using Core's LocalMediaNaming, splitting local library logic further.

**Why it is a problem:** Catalog, source health and local library logic is half in Core and half in App, so one feature such as local playback grouping or source probing needs coordinated edits in both projects. App-side classes like VodCacheService and LocalCachePlaybackCatalog contain domain logic that Core cannot reuse or test. Meanwhile AppServices is also responsible for unrelated concerns such as LibVLC and updates.

## 9. Scattered Functionality in OrionTV.Desktop.App.Views (OrionTV.Desktop.App)

**Designite:** The tool detected the smell in this component because a set of two or more components realizes the same high-level architectural concern. Following components realize the same concern: OrionTV.Desktop.App.Controls' OrionTV.Desktop.Core

**Classes:** OrionTV.Desktop.App.Controls.CardGrid; OrionTV.Desktop.Core.CatalogService; OrionTV.Desktop.Core.CatalogPlayabilityCache

**Commits that changed its files:** 1

**Emerged in:** b3ae88d60f 2026-07-22

**How:** This was already present in the only commit that touched CardGrid.xaml.cs, the initial import b3ae88d60f. CardGrid in OrionTV.Desktop.App.Controls manages its own ObservableCollection<CatalogItem> and implements item replacement and matching (ReplaceItem compares Source/Id/Title), paging triggers and empty-state handling. The same catalog-item concern is realized in Core by CatalogService and CatalogPlayabilityCache. No later commit changed CardGrid, so the smell has remained unchanged since the import.

**Timeline:**

- `b3ae88d60f`: CardGrid added with CatalogItem collection management and item-identity matching, overlapping Core's CatalogService/CatalogPlayabilityCache concern.

**Why it is a problem:** The rule for what makes two catalog items identical lives in a UI control (CardGrid.ReplaceItem) as well as in Core's catalog and cache classes. If Core changes item identity or playability keys, the grid's replacement logic can silently diverge, for example when HomeView replaces items after source-count queries.

## 10. Scattered Functionality in OrionTV.Desktop.App.Views (OrionTV.Desktop.App)

**Designite:** The tool detected the smell in this component because a set of two or more components realizes the same high-level architectural concern. Following components realize the same concern: OrionTV.Desktop.App' OrionTV.Desktop.App.LiveTranslation

**Classes:** OrionTV.Desktop.App.PlaybackController; OrionTV.Desktop.App.LiveTranslation.LiveTranslationController; OrionTV.Desktop.App.IAppHost; OrionTV.Desktop.App.AppServices

**Commits that changed its files:** 5

**Emerged in:** b3ae88d60f 2026-07-22

**How:** This was present in the initial import b3ae88d60f. LibVLC-based media handling is split between App (PlaybackController wraps MediaPlayer; AppServices owns the shared LibVLC instance via GetLibVlcAsync and is exposed through IAppHost) and LiveTranslation (LiveTranslationController runs its own LibVlcAudioTap with a separate LibVLC to extract audio from the same stream). f1bbae77f7 extended the App side further: PlaybackController gained Vout handling, explicit volume/mute state and pending-seek retries. AppServices gained a LibVlcMediaDecodeProbe built on GetLibVlcAsync, and Navigation.cs grew new playback parameters.

**Timeline:**

- `b3ae88d60f`: PlaybackController and AppServices (App) and LiveTranslationController (LiveTranslation) each manage LibVLC stream playback/consumption independently.
- `f1bbae77f7`: PlaybackController gains video-output and audio-state handling; AppServices adds another LibVLC consumer (LibVlcMediaDecodeProbe); Navigation.cs extends playback parameters.

**Why it is a problem:** Stream playback is handled in two places. LiveTranslationController deliberately creates a separate LibVLC pipeline instead of reusing the PlaybackController/AppServices infrastructure. Fixes to stream options, lifecycle or pausing (e.g. SetPaused coordination) must be repeated in both components, and LiveView has to keep them in sync by hand.

## 11. Scattered Functionality in OrionTV.Desktop.App.Views (OrionTV.Desktop.App)

**Designite:** The tool detected the smell in this component because a set of two or more components realizes the same high-level architectural concern. Following components realize the same concern: OrionTV.Desktop.Core' OrionTV.Desktop.App.LiveTranslation

**Classes:** OrionTV.Desktop.Core.GeminiLiveTranslateProtocol; OrionTV.Desktop.App.LiveTranslation.OpenAiCredentialStore; OrionTV.Desktop.Core.RollingSubtitleBuffer; OrionTV.Desktop.App.LiveTranslation.LiveTranslationController

**Commits that changed its files:** 1

**Emerged in:** b3ae88d60f 2026-07-22

**How:** This was present in the only commit that touched these files, the initial import b3ae88d60f. The live-translation concern is split: protocol and buffering logic (GeminiLiveTranslateProtocol, RollingSubtitleBuffer and the other provider protocols) live in OrionTV.Desktop.Core. Session orchestration (LiveTranslationController.CreateSession picks the provider and builds clients) and credential storage (OpenAiCredentialStore, which duplicates provider-alias parsing for gemini/doubao/deepgram) live in OrionTV.Desktop.App.LiveTranslation. No later commit changed these two files.

**Timeline:**

- `b3ae88d60f`: LiveTranslationController and OpenAiCredentialStore added in App.LiveTranslation, depending on Core's GeminiLiveTranslateProtocol/RollingSubtitleBuffer, splitting the translation concern across two components.

**Why it is a problem:** Adding or renaming a translation provider means editing Core's protocol resolution, the controller's CreateSession branching and the credential store's repeated provider-alias checks, all in different components. Provider identification is duplicated (ResolveProvider in Core versus the isGemini/isDoubao/isDeepgram string checks in OpenAiCredentialStore), which invites inconsistencies.

## 12. Scattered Functionality in OrionTV.Desktop.App.Views (OrionTV.Desktop.App)

**Designite:** The tool detected the smell in this component because a set of two or more components realizes the same high-level architectural concern. Following components realize the same concern: OrionTV.Desktop.App.LocalPlayback' OrionTV.Desktop.App

**Classes:** OrionTV.Desktop.App.LocalPlayback.MpvHost; OrionTV.Desktop.App.PlaybackController; OrionTV.Desktop.App.LocalPlayback.MpvLocalEngine; OrionTV.Desktop.App.IAppHost; OrionTV.Desktop.App.AppServices

**Commits that changed its files:** 7

**Emerged in:** b3ae88d60f 2026-07-22

**How:** This was present in the initial import b3ae88d60f. The playback concern is realized twice: the LibVLC PlaybackController in App (with the LibVLC instance supplied by AppServices through IAppHost), and MpvHost plus MpvLocalEngine in LocalPlayback. Both expose a near-identical API: SwitchTo/SwitchToAsync, TogglePlayPause, TrySeek, Volume, Mute, and StateChanged/TimeChanged/LengthChanged/EndReached. Later commits kept evolving the two in parallel. fe42a7f077 changed MpvHost DPI sizing and mpv OSC args. e1991e7308 added fullscreen sync and a seek-coalescing pump to MpvLocalEngine and native bounds syncing to MpvHost. f1bbae77f7 added the same HasVideoOutput/VideoOutputChanged feature to both PlaybackController and MpvLocalEngine, plus pending-seek logic in each, and AppServices and Navigation.cs changed alongside. 96434d1c40 added relative seek bursts and seek observation to MpvLocalEngine only.

**Timeline:**

- `b3ae88d60f`: PlaybackController/AppServices (App) and MpvHost/MpvLocalEngine (LocalPlayback) introduced as two parallel playback engines with mirrored APIs.
- `fe42a7f077`: MpvHost DPI handling and MpvLocalEngine OSC options changed independently of the LibVLC path.
- `e1991e7308`: MpvLocalEngine gains fullscreen and seek-coalescing logic; MpvHost gains SyncNativeBounds.
- `f1bbae77f7`: Both PlaybackController and MpvLocalEngine get duplicated video-output tracking and seek handling; AppServices and Navigation.cs updated.
- `96434d1c40`: MpvLocalEngine adds relative-seek burst and observation logic not mirrored in PlaybackController.

**Why it is a problem:** There is no shared playback abstraction, so features such as video-output detection or seek reliability must be implemented twice, in PlaybackController and MpvLocalEngine, as f1bbae77f7 shows. PlayerView then branches on _usingLocalEngine everywhere. Fixes made to only one engine (e.g. the seek bursts in 96434d1c40) let the two paths diverge.

## 13. God Component in OrionTV.Desktop.Core (OrionTV.Desktop.Core)

**Designite:** The tool detected the smell in this component because the component contains high number of classes. Number of classes in the component are: 56

**Classes:** OrionTV.Desktop.Core.AppleCmsUrlBuilder; OrionTV.Desktop.Core.AppleCmsEpisodeParser; OrionTV.Desktop.Core.SearchResultSources; OrionTV.Desktop.Core.AppleCmsMapper; OrionTV.Desktop.Core.AppleCmsClient; OrionTV.Desktop.Core.CatalogPlayabilityStatus; OrionTV.Desktop.Core.CatalogTitleMatcher; OrionTV.Desktop.Core.CatalogPlayabilityBadge; OrionTV.Desktop.Core.CatalogPlayabilityCache; OrionTV.Desktop.Core.PlaybackResumePolicy; OrionTV.Desktop.Core.PlaybackFallbackSelector; OrionTV.Desktop.Core.PlaybackMediaOptions; OrionTV.Desktop.Core.PlaybackStartupWatchdog; OrionTV.Desktop.Core.PlaybackStartupSignal; OrionTV.Desktop.Core.PlaybackStartupPolicy; OrionTV.Desktop.Core.CatalogService; OrionTV.Desktop.Core.ChannelHealth; OrionTV.Desktop.Core.MediaProbeStatus; OrionTV.Desktop.Core.ChannelHealthScoring; OrionTV.Desktop.Core.ChannelHealthDisplay; OrionTV.Desktop.Core.ChannelHealthProbe; OrionTV.Desktop.Core.DeepgramSttProtocol; OrionTV.Desktop.Core.DesktopLiveSourceSettings; OrionTV.Desktop.Core.DoubanClient; OrionTV.Desktop.Core.DoubaoAstProtocol; OrionTV.Desktop.Core.ExtraVideoSourcesStore; OrionTV.Desktop.Core.VideoSourceMerger; OrionTV.Desktop.Core.AiImportPromptBuilder; OrionTV.Desktop.Core.GeminiLiveTranslateProtocol; OrionTV.Desktop.Core.HlsAdSkip; OrionTV.Desktop.Core.HomeCategoryMatcher; OrionTV.Desktop.Core.IVodSourceClient; OrionTV.Desktop.Core.VodSourceClientFactory; OrionTV.Desktop.Core.UnsupportedVodSourceClient; OrionTV.Desktop.Core.LocalMediaNaming; OrionTV.Desktop.Core.NaturalPathComparer; OrionTV.Desktop.Core.LocalMediaStore; OrionTV.Desktop.Core.JsonDictionaryStore<T>; OrionTV.Desktop.Core.FavoriteStore; OrionTV.Desktop.Core.PlayRecordStore; OrionTV.Desktop.Core.M3uParser; OrionTV.Desktop.Core.MacCmsJsonClient; OrionTV.Desktop.Core.MacCmsXmlClient; OrionTV.Desktop.Core.VideoSourceProtocols; OrionTV.Desktop.Core.EpisodeLabelFormatter; OrionTV.Desktop.Core.AppleCmsVodItem; OrionTV.Desktop.Core.RealtimeTranslationEventKind; OrionTV.Desktop.Core.RealtimeTranslationProtocol; OrionTV.Desktop.Core.Pcm16TranslationFrameBuffer; OrionTV.Desktop.Core.RollingSubtitleBuffer; OrionTV.Desktop.Core.DesktopPaths; OrionTV.Desktop.Core.VodCacheSettings; OrionTV.Desktop.Core.DesktopSettingsMigration; OrionTV.Desktop.Core.DesktopSettingsForm; OrionTV.Desktop.Core.SettingsStore; OrionTV.Desktop.Core.VideoSourceSubscriptionParser

**Commits that changed its files:** 5

**Emerged in:** b3ae88d60f 2026-07-22

**How:** The smell was already present in the first commit that touched these files. Commit b3ae88d60f ('publish source-free OrionTV') imported 21 of the 22 listed files into the single OrionTV.Desktop.Core namespace/project at once. Together they hold roughly 45 of the 56 participating classes, already well beyond a God Component class-count threshold. Those classes cover many unrelated concerns: AppleCMS/MacCMS JSON/XML source clients and URL/episode parsing (AppleCmsUrlBuilder, AppleCmsEpisodeParser, AppleCmsMapper, AppleCmsClient, MacCmsJsonClient, MacCmsXmlClient, IVodSourceClient, VodSourceClientFactory, UnsupportedVodSourceClient), the Douban catalogue client and home/catalog orchestration (DoubanClient, CatalogService, HomeCategoryMatcher, CatalogPlayability*), live-TV M3U parsing, multi-source merging and channel health probing (M3uParser, DesktopLiveSourceSettings, ChannelHealth*), HLS ad skipping (HlsAdSkip), four AI live-translation/STT wire protocols (RealtimeTranslationProtocol, GeminiLiveTranslateProtocol, DoubaoAstProtocol, DeepgramSttProtocol, Pcm16TranslationFrameBuffer), subscription and extra-source import including AI prompt building (VideoSourceSubscriptionParser, ExtraVideoSourcesStore, AiImportPromptBuilder), JSON file persistence (JsonDictionaryStore<T>, FavoriteStore, PlayRecordStore) and settings/paths (DesktopPaths, VodCacheSettings, DesktopSettingsMigration, DesktopSettingsForm, SettingsStore). Commit 0c5495360e only changed prompt strings and did not affect the smell. Later commits made it worse by adding more classes to the same component. fe42a7f077 added LocalMediaLibrary.cs with a new local-media-library concern (LocalMediaNaming, NaturalPathComparer, LocalMediaStore) and extended PlayRecordItem/PlayRecordStore and DesktopPaths for it. f1bbae77f7 added MediaProbeStatus to ChannelHealthProbe.cs, EpisodeLabelFormatter to Models.cs and PlaybackResumePolicy to CatalogModels.cs. The other playback classes (PlaybackFallbackSelector, PlaybackMediaOptions, PlaybackStartupWatchdog, PlaybackStartupSignal, PlaybackStartupPolicy) are most likely in the cut-off part of the CatalogModels.cs diff, but that part is not visible. e137971afc grew PlayRecordStore with history aggregation that depends on CatalogTitleMatcher, but it added no listed class. The end result is 56 classes.

**Timeline:**

- `b3ae88d60f`: Initial import of 21 Core files with ~45 classes spanning VOD source protocols, Douban catalogue, live TV/M3U and channel health probing, HLS ad skip, four AI translation protocols, subscription/AI import, JSON stores and settings, all in one component.
- `fe42a7f077`: Added LocalMediaLibrary.cs (LocalMediaNaming, NaturalPathComparer, LocalMediaStore), a new local-media-library responsibility. Extended PlayRecordItem, PlayRecordStore and DesktopPaths for local media.
- `f1bbae77f7`: Added playback and resume policy types (PlaybackResumePolicy, EpisodeLabelFormatter, MediaProbeStatus, plus the Playback* startup/fallback classes, likely in CatalogModels.cs). Greatly expanded ChannelHealthProbe with media validation, bringing the component to 56 classes.
- `e137971afc`: Grew PlayRecordStore with media-level history aggregation coupled to CatalogTitleMatcher, adding more responsibility to the existing store classes.

**Why it is a problem:** OrionTV.Desktop.Core mixes CMS scraping clients, Douban integration, live-TV health probing, HLS ad detection, OpenAI/Gemini/Doubao/Deepgram speech-translation wire protocols, local media scanning and JSON persistence in one namespace. Any change, such as a new translation provider or source protocol, recompiles and risks the whole core, and the pieces cannot be reused or tested in isolation. Cross-cutting shortcuts like PlayRecordStore depending on CatalogTitleMatcher, or the settings record referencing Doubao and Gemini protocol constants, show how the lack of internal boundaries lets unrelated features become entangled.

## 14. Feature Concentration in OrionTV.Desktop.Tests (OrionTV.Desktop.Tests)

**Designite:** The tool detected the smell in this component because the component realizes more than one architectural concern/feature. Independent sets of related classes within this component are: [AiCliLauncherTests]' [AppleCmsServiceTests' StubHandler' VodProtocolTests]' [ChannelHealthScoringTests' RecordingHandler' FlvResponseHandler' HtmlResponseHandler' MisleadingHtmlResponseHandler' EncryptedHlsHandler' HtmlSegmentHandler' VariantRecordingHandler]' [DesktopSettingsTests]' [LocalStoreTests' TestStringStore]' [DesktopUpdateServiceTests' StubHttpMessageHandler' InlineProgress]' [ExtraVideoSourcesTests]' [HlsAdSkipTests]' [HomeCategoryMatcherTests]' [LocalCachePlaybackCatalogTests]' [LocalMediaLibraryTests]' [M3uParserTests]' [MpvLocalEngineTests]' [PlaybackResumePolicyTests]' [WpfNavigationCollection' PlayerNavigationSurfaceTests]' [PlayerShortcutTests]' [PlayRecordHistoryTests]' [RealtimeTranslationProtocolTests]' [GeminiLiveTranslateProtocolTests]' [DeepgramSttProtocolTests]' [DoubaoAstProtocolTests]' [SubscriptionParserTests]' [VodCacheLookupTests]' [VodCacheServiceTests' InlineProgress<T>' BlockingFirstProgress' FakeHlsServer]' [VodSourceHealthProbeTests' StubDecodeProbe]. LCC (Lack of Component Cohesion) = 0'6

**Classes:** OrionTV.Desktop.Tests.AiCliLauncherTests; OrionTV.Desktop.Tests.AppleCmsServiceTests; OrionTV.Desktop.Tests.StubHandler; OrionTV.Desktop.Tests.ChannelHealthScoringTests; OrionTV.Desktop.Tests.RecordingHandler; OrionTV.Desktop.Tests.FlvResponseHandler; OrionTV.Desktop.Tests.HtmlResponseHandler; OrionTV.Desktop.Tests.MisleadingHtmlResponseHandler; OrionTV.Desktop.Tests.EncryptedHlsHandler; OrionTV.Desktop.Tests.HtmlSegmentHandler; OrionTV.Desktop.Tests.VariantRecordingHandler; OrionTV.Desktop.Tests.DesktopSettingsTests; OrionTV.Desktop.Tests.LocalStoreTests; OrionTV.Desktop.Tests.TestStringStore; OrionTV.Desktop.Tests.DesktopUpdateServiceTests; OrionTV.Desktop.Tests.StubHttpMessageHandler; OrionTV.Desktop.Tests.InlineProgress; OrionTV.Desktop.Tests.ExtraVideoSourcesTests; OrionTV.Desktop.Tests.HlsAdSkipTests; OrionTV.Desktop.Tests.HomeCategoryMatcherTests; OrionTV.Desktop.Tests.LocalCachePlaybackCatalogTests; OrionTV.Desktop.Tests.LocalMediaLibraryTests; OrionTV.Desktop.Tests.M3uParserTests; OrionTV.Desktop.Tests.MpvLocalEngineTests; OrionTV.Desktop.Tests.PlaybackResumePolicyTests; OrionTV.Desktop.Tests.WpfNavigationCollection; OrionTV.Desktop.Tests.PlayerNavigationSurfaceTests; OrionTV.Desktop.Tests.PlayerShortcutTests; OrionTV.Desktop.Tests.PlayRecordHistoryTests; OrionTV.Desktop.Tests.RealtimeTranslationProtocolTests; OrionTV.Desktop.Tests.GeminiLiveTranslateProtocolTests; OrionTV.Desktop.Tests.DeepgramSttProtocolTests; OrionTV.Desktop.Tests.DoubaoAstProtocolTests; OrionTV.Desktop.Tests.SubscriptionParserTests; OrionTV.Desktop.Tests.VodCacheLookupTests; OrionTV.Desktop.Tests.VodCacheServiceTests; OrionTV.Desktop.Tests.InlineProgress<T>; OrionTV.Desktop.Tests.BlockingFirstProgress; OrionTV.Desktop.Tests.FakeHlsServer; OrionTV.Desktop.Tests.VodProtocolTests; OrionTV.Desktop.Tests.VodSourceHealthProbeTests; OrionTV.Desktop.Tests.StubDecodeProbe

**Commits that changed its files:** 9

**Emerged in:** b3ae88d60f 2026-07-22

**How:** The smell was already present in the first commit that touched these files. In b3ae88d60f ('publish source-free OrionTV') the single test project received a batch of fixtures that do not use each other and cover unrelated product features: AI CLI launching (AiCliLauncherTests), AppleCMS/MacCMS catalog clients (AppleCmsServiceTests and VodProtocolTests with StubHandler), live-channel health probing (ChannelHealthScoringTests with RecordingHandler and FlvResponseHandler), settings (DesktopSettingsTests), extra video sources and AI prompts (ExtraVideoSourcesTests), HLS ad skipping (HlsAdSkipTests), home category matching, M3U parsing, subscription parsing, realtime translation protocols (RealtimeTranslationProtocolTests and GeminiLiveTranslateProtocolTests in the same file), and the VOD download cache (VodCacheServiceTests with FakeHlsServer). That is already many independent class groups in one component, so the low-cohesion condition was met from the start. Later commits added more unrelated islands instead of splitting the project. fe42a7f077 added LocalMediaLibraryTests, which also exercises PlayRecordStore. e1991e7308 added MpvLocalEngineTests for the mpv local player. f1bbae77f7 added DesktopUpdateServiceTests (installer download/verification with StubHttpMessageHandler and InlineProgress), PlaybackResumePolicyTests, PlayerShortcutTests (WPF keys), VodCacheLookupTests and VodSourceHealthProbeTests (with StubDecodeProbe). The same commit put five more HTTP handler fakes into ChannelHealthScoringTests. c601eb789d added WPF UI navigation tests (WpfNavigationCollection, PlayerNavigationSurfaceTests). e137971afc added LocalCachePlaybackCatalogTests, PlayRecordHistoryTests, and InlineProgress<T> and BlockingFirstProgress inside VodCacheServiceTests. The files for LocalStoreTests/TestStringStore and for the Deepgram/Doubao protocol tests are not shown in the visible diffs; they were probably in the truncated parts of the initial files.

**Timeline:**

- `b3ae88d60f`: Initial import put tests for AI CLI, CMS catalog protocols, channel health, settings, extra sources, ad skipping, category matching, M3U, subscriptions, realtime translation and the VOD cache into one test component. These are independent class groups from the start.
- `fe42a7f077`: Added LocalMediaLibraryTests, a new independent group for local media naming/import and play-record persistence.
- `e1991e7308`: Added MpvLocalEngineTests, another isolated concern (mpv player argument building).
- `f1bbae77f7`: Added unrelated groups for the self-updater, resume policy, player shortcuts, VOD cache lookup and VOD source health probing. Also expanded the channel-health fakes with five more handler classes.
- `c601eb789d`: Added WPF navigation UI tests (WpfNavigationCollection, PlayerNavigationSurfaceTests), mixing UI-thread integration tests into the same component.
- `e137971afc`: Added LocalCachePlaybackCatalogTests and PlayRecordHistoryTests plus extra progress helpers in VodCacheServiceTests, increasing the number of disconnected groups.

**Why it is a problem:** One assembly mixes fast pure-logic tests (M3U, ad-skip, category matching) with process-spawning PowerShell tests, a TCP-based FakeHlsServer, STA-thread WPF window tests and network integration tests. Every feature change in Core or App touches the same project, and nobody can run or own one feature's tests in isolation. Helpers such as StubHandler, StubHttpMessageHandler, InlineProgress and InlineProgress<T> get re-invented per file instead of shared, because nothing groups the related fixtures.

## 15. God Component in OrionTV.Desktop.Tests (OrionTV.Desktop.Tests)

**Designite:** The tool detected the smell in this component because the component contains high number of classes. Number of classes in the component are: 42

**Classes:** OrionTV.Desktop.Tests.AiCliLauncherTests; OrionTV.Desktop.Tests.AppleCmsServiceTests; OrionTV.Desktop.Tests.StubHandler; OrionTV.Desktop.Tests.ChannelHealthScoringTests; OrionTV.Desktop.Tests.RecordingHandler; OrionTV.Desktop.Tests.FlvResponseHandler; OrionTV.Desktop.Tests.HtmlResponseHandler; OrionTV.Desktop.Tests.MisleadingHtmlResponseHandler; OrionTV.Desktop.Tests.EncryptedHlsHandler; OrionTV.Desktop.Tests.HtmlSegmentHandler; OrionTV.Desktop.Tests.VariantRecordingHandler; OrionTV.Desktop.Tests.DesktopSettingsTests; OrionTV.Desktop.Tests.LocalStoreTests; OrionTV.Desktop.Tests.TestStringStore; OrionTV.Desktop.Tests.DesktopUpdateServiceTests; OrionTV.Desktop.Tests.StubHttpMessageHandler; OrionTV.Desktop.Tests.InlineProgress; OrionTV.Desktop.Tests.ExtraVideoSourcesTests; OrionTV.Desktop.Tests.HlsAdSkipTests; OrionTV.Desktop.Tests.HomeCategoryMatcherTests; OrionTV.Desktop.Tests.LocalCachePlaybackCatalogTests; OrionTV.Desktop.Tests.LocalMediaLibraryTests; OrionTV.Desktop.Tests.M3uParserTests; OrionTV.Desktop.Tests.MpvLocalEngineTests; OrionTV.Desktop.Tests.PlaybackResumePolicyTests; OrionTV.Desktop.Tests.WpfNavigationCollection; OrionTV.Desktop.Tests.PlayerNavigationSurfaceTests; OrionTV.Desktop.Tests.PlayerShortcutTests; OrionTV.Desktop.Tests.PlayRecordHistoryTests; OrionTV.Desktop.Tests.RealtimeTranslationProtocolTests; OrionTV.Desktop.Tests.GeminiLiveTranslateProtocolTests; OrionTV.Desktop.Tests.DeepgramSttProtocolTests; OrionTV.Desktop.Tests.DoubaoAstProtocolTests; OrionTV.Desktop.Tests.SubscriptionParserTests; OrionTV.Desktop.Tests.VodCacheLookupTests; OrionTV.Desktop.Tests.VodCacheServiceTests; OrionTV.Desktop.Tests.InlineProgress<T>; OrionTV.Desktop.Tests.BlockingFirstProgress; OrionTV.Desktop.Tests.FakeHlsServer; OrionTV.Desktop.Tests.VodProtocolTests; OrionTV.Desktop.Tests.VodSourceHealthProbeTests; OrionTV.Desktop.Tests.StubDecodeProbe

**Commits that changed its files:** 9

**Emerged in:** f1bbae77f7 2026-07-27

**How:** Counting backwards from the final 42 classes using the classes each commit visibly added gives the following growth. b3ae88d60f started the component with about 21 classes: the test fixtures, StubHandler, RecordingHandler, FlvResponseHandler, FakeHlsServer, and the translation protocol test classes. fe42a7f077 added LocalMediaLibraryTests (about 22). e1991e7308 added MpvLocalEngineTests (about 23). f1bbae77f7 ('prepare desktop 1.3.15 release') was the big jump of about 13 classes. Five were HTTP handler fakes in ChannelHealthScoringTests (HtmlResponseHandler, MisleadingHtmlResponseHandler, EncryptedHlsHandler, HtmlSegmentHandler, VariantRecordingHandler). The rest were DesktopUpdateServiceTests with StubHttpMessageHandler and InlineProgress, PlaybackResumePolicyTests, PlayerShortcutTests, VodCacheLookupTests, and VodSourceHealthProbeTests with StubDecodeProbe. That raised the count to about 36, which crosses Designite's usual class-count threshold, so this is the first commit where the component counts as a God Component. c601eb789d added WpfNavigationCollection and PlayerNavigationSurfaceTests (about 38). e137971afc added LocalCachePlaybackCatalogTests, PlayRecordHistoryTests, InlineProgress<T> and BlockingFirstProgress, reaching 42. The exact count for the initial commit depends on classes hidden in truncated diffs (e.g. LocalStoreTests, TestStringStore, Deepgram/Doubao tests). Even so, the arithmetic consistently places the threshold crossing at f1bbae77f7.

**Timeline:**

- `b3ae88d60f`: Created the test component with roughly 21 classes across many feature test files and nested fakes.
- `fe42a7f077`: Added LocalMediaLibraryTests.
- `e1991e7308`: Added MpvLocalEngineTests.
- `f1bbae77f7`: Added about 13 classes (five probe handler fakes, update service tests and stubs, resume/shortcut/cache-lookup/source-probe tests and StubDecodeProbe), pushing the component past the size threshold.
- `c601eb789d`: Added WpfNavigationCollection and PlayerNavigationSurfaceTests.
- `e137971afc`: Added LocalCachePlaybackCatalogTests, PlayRecordHistoryTests, InlineProgress<T> and BlockingFirstProgress, reaching 42 classes.

**Why it is a problem:** Each release commit (1.3.15, 1.3.16, 1.3.17) dumps more fixtures and private fakes into the one OrionTV.Desktop.Tests project, so it keeps growing alongside both Core and App. Its 42 classes cover CMS clients, live-channel probes, translation protocols, updater, mpv, WPF navigation and the VOD cache. That makes the suite slow and hard to navigate, and fragile to run as a whole: a heavy test such as the STA WPF test or the PowerShell launcher test affects every unrelated feature's feedback loop.
