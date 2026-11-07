# How the architectural smells of zo1223/OpaiTV emerged

## 1. Cyclic Dependency in OrionTV.Desktop.App (OrionTV.Desktop.App)

**Designite:** The tool detected the smell in this component because this component participates in a cyclic dependency. The participating components in the cycle are: OrionTV.Desktop.App' OrionTV.Desktop.App.Views

**Classes:** OrionTV.Desktop.App.AiCliLauncher; OrionTV.Desktop.App.MainWindow; OrionTV.Desktop.App.Views.AiImportDialog; OrionTV.Desktop.App.Views.LiveView; OrionTV.Desktop.App.Views.PlayerView

**Commits that changed its files:** 9

**Emerged in:** b3ae88d60f 2026-07-22

**How:** The cycle was already there in the first commit, b3ae88d60f ('publish source-free OrionTV'), which imported the whole desktop app in one go. In that commit MainWindow (namespace OrionTV.Desktop.App) does `using OrionTV.Desktop.App.Views` and creates HomeView, LiveView, SettingsView, PlayerView and the other pages in CreateView. That is the App → Views edge. The Views depend back on the root namespace: AiImportDialog calls AiCliLauncher.ResolveDocsDirectory/Launch/LaunchDiscovery, and LiveView and PlayerView use PlaybackController and the PlaybackState enum declared in PlaybackController.cs. Later commits made both directions stronger. f1bbae77f7 grew MainWindow by about 200 lines and rewrote PlayerView (+1070 lines), which now handles PlaybackState in Controller_StateChanged. e137971afc added SectionNavigationState in MainWindow and the INavigationVisibilityAware interface in Navigation.cs, which LiveView now implements.

**Timeline:**

- `b3ae88d60f`: Initial import: MainWindow creates all Views (App→Views); AiImportDialog calls AiCliLauncher, and LiveView/PlayerView use PlaybackController/PlaybackState (Views→App)
- `f1bbae77f7`: MainWindow and PlayerView greatly expanded; PlayerView adds more state handling against App's PlaybackState/PlaybackController
- `e137971afc`: MainWindow adds per-section view state over the Views; LiveView implements the new App-level INavigationVisibilityAware interface

**Why it is a problem:** The shell (MainWindow) builds the pages, and the pages reach back into root-namespace services (AiCliLauncher) and playback types (PlaybackState), so neither namespace can be built or tested without the other. A change to PlaybackController's state model or to MainWindow's navigation ripples into LiveView and PlayerView and back again. As a result, no page can be reused outside this one window.

## 2. Cyclic Dependency in OrionTV.Desktop.App (OrionTV.Desktop.App)

**Designite:** The tool detected the smell in this component because this component participates in a cyclic dependency. The participating components in the cycle are: OrionTV.Desktop.App' OrionTV.Desktop.App.Views' OrionTV.Desktop.App.LocalPlayback

**Classes:** OrionTV.Desktop.App.AiCliLauncher; OrionTV.Desktop.App.MainWindow; OrionTV.Desktop.App.Views.AiImportDialog; OrionTV.Desktop.App.Views.LiveView; OrionTV.Desktop.App.Views.PlayerView; OrionTV.Desktop.App.LocalPlayback.MpvLocalEngine

**Commits that changed its files:** 9

**Emerged in:** b3ae88d60f 2026-07-22

**How:** This cycle was also present from the initial import, b3ae88d60f. It runs App → Views (MainWindow creates PlayerView and the other pages), then Views → LocalPlayback (PlayerView does `using OrionTV.Desktop.App.LocalPlayback`, hosts MpvHost in XAML and creates `new MpvLocalEngine(hwnd, Dispatcher)`), then LocalPlayback → App (MpvLocalEngine keeps `PlaybackState _state = PlaybackState.Idle`, and PlaybackState is the enum declared in App/PlaybackController.cs). The Views → App edges of smell 1 (AiImportDialog→AiCliLauncher, LiveView/PlayerView→PlaybackState) also take part. Later commits kept the cycle alive and made it larger: e1991e7308 (+293 lines), f1bbae77f7 and 96434d1c40 reworked MpvLocalEngine and its state machine, which is still written in terms of App's PlaybackState. Several of the same commits (e1991e7308, f1bbae77f7, 96434d1c40) also extended PlayerView's use of the mpv engine.

**Timeline:**

- `b3ae88d60f`: Initial import: MainWindow→Views, PlayerView→MpvLocalEngine/MpvHost, and MpvLocalEngine→PlaybackState (App) close the cycle
- `e1991e7308`: MpvLocalEngine (+293 lines) and PlayerView extended; the engine keeps reporting state through App's PlaybackState
- `f1bbae77f7`: MpvLocalEngine, PlayerView, PlaybackController and MainWindow all extended further
- `96434d1c40`: MpvLocalEngine extended again (+176 lines) and still coupled to App's PlaybackState

**Why it is a problem:** The mpv playback engine is meant to be a low-level, reusable component. Here it depends on an enum that lives next to the LibVLC PlaybackController in the app shell, and the shell reaches it only through PlayerView. Because of this three-namespace loop, the local playback engine cannot be extracted or tested without the views and the main window. Any change to PlaybackState also affects both playback back-ends and the player UI.

## 3. Feature Concentration in OrionTV.Desktop.App (OrionTV.Desktop.App)

**Designite:** The tool detected the smell in this component because the component realizes more than one architectural concern/feature. Independent sets of related classes within this component are: [AiCliTool' AiCliLauncher' AiCliTaskMode' MainWindow' SectionNavigationState' AppPage' IAppHost' INavigationAware' INavigationVisibilityAware' AiSourceWatcher' ChangeKind' AppServices' DesktopUpdateService' PlaybackController' VodCacheService' InlineProgress<T>' VodCacheLog' VodDownloadManager' Job' VodPlayableSourceResolver' VodSourceProbeStatus' VodSourceHealthDisplay' VodSourceHealthProbe' LibVlcMediaDecodeProbe' WindowMessage' HlsAesDecryptMerger' VodCacheSession' CacheFile' PlaybackState' VodDownloadJobStatus' MediaDecodeProbeStatus' IMediaDecodeProbe' VodSourceProbeSampler]' [App]' [EmptyStringToVisibilityConverter]' [ImageLoader]' [LiveChannelViewModel]' [LocalCachePlaybackCatalog]' [OsdController]' [PlayerKeyboardHook' KbdLlHookStruct]' [VodCacheLookup]. LCC (Lack of Component Cohesion) = 0'21

**Classes:** OrionTV.Desktop.App.AiCliTool; OrionTV.Desktop.App.AiCliLauncher; OrionTV.Desktop.App.AiCliTaskMode; OrionTV.Desktop.App.AiSourceWatcher; OrionTV.Desktop.App.ChangeKind; OrionTV.Desktop.App.App; OrionTV.Desktop.App.AppServices; OrionTV.Desktop.App.DesktopUpdateService; OrionTV.Desktop.App.EmptyStringToVisibilityConverter; OrionTV.Desktop.App.HlsAesDecryptMerger; OrionTV.Desktop.App.ImageLoader; OrionTV.Desktop.App.LiveChannelViewModel; OrionTV.Desktop.App.LocalCachePlaybackCatalog; OrionTV.Desktop.App.MainWindow; OrionTV.Desktop.App.SectionNavigationState; OrionTV.Desktop.App.AppPage; OrionTV.Desktop.App.IAppHost; OrionTV.Desktop.App.INavigationAware; OrionTV.Desktop.App.INavigationVisibilityAware; OrionTV.Desktop.App.OsdController; OrionTV.Desktop.App.PlaybackState; OrionTV.Desktop.App.PlaybackController; OrionTV.Desktop.App.PlayerKeyboardHook; OrionTV.Desktop.App.KbdLlHookStruct; OrionTV.Desktop.App.VodCacheLookup; OrionTV.Desktop.App.VodCacheSession; OrionTV.Desktop.App.CacheFile; OrionTV.Desktop.App.VodCacheService; OrionTV.Desktop.App.InlineProgress<T>; OrionTV.Desktop.App.VodCacheLog; OrionTV.Desktop.App.VodDownloadJobStatus; OrionTV.Desktop.App.VodDownloadManager; OrionTV.Desktop.App.Job; OrionTV.Desktop.App.VodPlayableSourceResolver; OrionTV.Desktop.App.VodSourceProbeStatus; OrionTV.Desktop.App.MediaDecodeProbeStatus; OrionTV.Desktop.App.IMediaDecodeProbe; OrionTV.Desktop.App.VodSourceProbeSampler; OrionTV.Desktop.App.VodSourceHealthDisplay; OrionTV.Desktop.App.VodSourceHealthProbe; OrionTV.Desktop.App.LibVlcMediaDecodeProbe; OrionTV.Desktop.App.WindowMessage

**Commits that changed its files:** 8

**Emerged in:** b3ae88d60f 2026-07-22

**How:** The initial import, b3ae88d60f, already put unrelated concerns into the root OrionTV.Desktop.App namespace: AI CLI launching (AiCliLauncher, AiCliTool, AiCliTaskMode), file watching (AiSourceWatcher), navigation (MainWindow, AppPage, IAppHost, INavigationAware), LibVLC playback (PlaybackController, PlaybackState), VOD caching (VodCacheService, VodCacheSession, CacheFile, VodCacheLog, HlsAesDecryptMerger), downloads (VodDownloadManager, Job), plus the App class, a WPF converter, ImageLoader, LiveChannelViewModel and OsdController. Classes such as App, EmptyStringToVisibilityConverter, ImageLoader, LiveChannelViewModel and OsdController share no relations with the rest, so they form separate groups. f1bbae77f7 added more unrelated features: DesktopUpdateService, PlayerKeyboardHook with KbdLlHookStruct (a new isolated group), VodCacheLookup (another isolated group), VodPlayableSourceResolver and the whole VodSourceHealthProbe family. e137971afc added LocalCachePlaybackCatalog (another isolated group), the SectionNavigationState and INavigationVisibilityAware navigation types, and InlineProgress<T> in VodCacheService.

**Timeline:**

- `b3ae88d60f`: Root namespace imported with AI-CLI, navigation, playback, caching, download, converter, image loading, live view-model and OSD concerns mixed together
- `f1bbae77f7`: Added DesktopUpdateService, PlayerKeyboardHook/KbdLlHookStruct, VodCacheLookup, VodPlayableSourceResolver and the VodSourceHealthProbe types to the same namespace
- `e137971afc`: Added LocalCachePlaybackCatalog, SectionNavigationState, INavigationVisibilityAware and InlineProgress<T>

**Why it is a problem:** Low-level Win32 keyboard hooks, an HTTP self-updater, an HLS AES decryptor/cache proxy, source health probing and AI terminal launching all sit in one namespace next to the WPF shell. The namespace has no single reason to change, and its LCC is very low (0.21). A change to any one feature, such as caching or updates, touches the component every page depends on, and none of these features can be moved out or reused on its own.

## 4. God Component in OrionTV.Desktop.App (OrionTV.Desktop.App)

**Designite:** The tool detected the smell in this component because the component contains high number of classes. Number of classes in the component are: 42

**Classes:** OrionTV.Desktop.App.AiCliTool; OrionTV.Desktop.App.AiCliLauncher; OrionTV.Desktop.App.AiCliTaskMode; OrionTV.Desktop.App.AiSourceWatcher; OrionTV.Desktop.App.ChangeKind; OrionTV.Desktop.App.App; OrionTV.Desktop.App.AppServices; OrionTV.Desktop.App.DesktopUpdateService; OrionTV.Desktop.App.EmptyStringToVisibilityConverter; OrionTV.Desktop.App.HlsAesDecryptMerger; OrionTV.Desktop.App.ImageLoader; OrionTV.Desktop.App.LiveChannelViewModel; OrionTV.Desktop.App.LocalCachePlaybackCatalog; OrionTV.Desktop.App.MainWindow; OrionTV.Desktop.App.SectionNavigationState; OrionTV.Desktop.App.AppPage; OrionTV.Desktop.App.IAppHost; OrionTV.Desktop.App.INavigationAware; OrionTV.Desktop.App.INavigationVisibilityAware; OrionTV.Desktop.App.OsdController; OrionTV.Desktop.App.PlaybackState; OrionTV.Desktop.App.PlaybackController; OrionTV.Desktop.App.PlayerKeyboardHook; OrionTV.Desktop.App.KbdLlHookStruct; OrionTV.Desktop.App.VodCacheLookup; OrionTV.Desktop.App.VodCacheSession; OrionTV.Desktop.App.CacheFile; OrionTV.Desktop.App.VodCacheService; OrionTV.Desktop.App.InlineProgress<T>; OrionTV.Desktop.App.VodCacheLog; OrionTV.Desktop.App.VodDownloadJobStatus; OrionTV.Desktop.App.VodDownloadManager; OrionTV.Desktop.App.Job; OrionTV.Desktop.App.VodPlayableSourceResolver; OrionTV.Desktop.App.VodSourceProbeStatus; OrionTV.Desktop.App.MediaDecodeProbeStatus; OrionTV.Desktop.App.IMediaDecodeProbe; OrionTV.Desktop.App.VodSourceProbeSampler; OrionTV.Desktop.App.VodSourceHealthDisplay; OrionTV.Desktop.App.VodSourceHealthProbe; OrionTV.Desktop.App.LibVlcMediaDecodeProbe; OrionTV.Desktop.App.WindowMessage

**Commits that changed its files:** 8

**Emerged in:** f1bbae77f7 2026-07-27

**How:** Counting non-record types the way Designite lists them, the initial import b3ae88d60f put about 26 classes, interfaces and enums into the root OrionTV.Desktop.App namespace. These included AiCliLauncher, AiSourceWatcher, App, AppServices, MainWindow, the navigation types, PlaybackController, VodCacheService and its helpers, VodDownloadManager and Job, and LocalMediaRemuxer. Commit f1bbae77f7 ('prepare desktop 1.3.15 release') added 13 more types in one step: DesktopUpdateService, PlayerKeyboardHook and KbdLlHookStruct, VodCacheLookup, VodPlayableSourceResolver, and VodSourceHealthProbe.cs with VodSourceProbeStatus, MediaDecodeProbeStatus, IMediaDecodeProbe, VodSourceProbeSampler, VodSourceHealthDisplay, VodSourceHealthProbe, LibVlcMediaDecodeProbe and WindowMessage. That brought the count to about 39 and past the class-count threshold. 96434d1c40 removed LocalMediaRemuxer (about 38). e137971afc added LocalCachePlaybackCatalog, SectionNavigationState, INavigationVisibilityAware and InlineProgress<T>, which gives the 42 classes reported. The exact threshold is assumed to be Designite's default of about 30 classes; the counts themselves were checked in the code.

**Timeline:**

- `b3ae88d60f`: Root namespace created with about 26 types
- `f1bbae77f7`: 13 more types (update service, keyboard hook, cache lookup, playable-source resolver, source health probe family) push the count to about 39
- `96434d1c40`: LocalMediaRemuxer removed (minor reduction)
- `e137971afc`: LocalCachePlaybackCatalog, SectionNavigationState, INavigationVisibilityAware and InlineProgress<T> bring it to 42

**Why it is a problem:** Almost every non-UI service of the desktop player lands in the single root namespace, which has become a catch-all. The project already has separate sub-namespaces (LocalPlayback, LiveTranslation, Controls), so features such as caching, source probing and updating could have their own homes. Instead, each release adds more classes here, and the namespace becomes harder to understand and to change safely.

## 5. Unstable Dependency in OrionTV.Desktop.App (OrionTV.Desktop.App)

**Designite:** The tool detected the smell in this component because this component depends on other components that are less stable than itself. This component depends on following less stable component(s): OrionTV.Desktop.App.Views

**Classes:** OrionTV.Desktop.App.AiImportDialog; OrionTV.Desktop.App.DetailView; OrionTV.Desktop.App.FavoritesView; OrionTV.Desktop.App.HomeView; OrionTV.Desktop.App.LiveView; OrionTV.Desktop.App.LocalVideoView; OrionTV.Desktop.App.PlayerView; OrionTV.Desktop.App.SearchView; OrionTV.Desktop.App.SettingsView

**Commits that changed its files:** 8

**Emerged in:** b3ae88d60f 2026-07-22

**How:** The dependency was introduced with the initial import, b3ae88d60f. MainWindow in the root namespace imports OrionTV.Desktop.App.Views and creates every page. The Views namespace depends on many namespaces (Core, the root App namespace, Controls, LiveTranslation, LocalPlayback), but only MainWindow depends on it. So Views is highly unstable, while the root namespace is depended on by Views, Controls (VideoCardControl uses ImageLoader) and LocalPlayback (MpvLocalEngine uses PlaybackState), which makes it comparatively stable. The namespace-level dependency graph checked at the analyzed version is the same as in the initial import, so the stable-depends-on-unstable relation has existed since then. Later commits made it heavier: f1bbae77f7 and e137971afc grew MainWindow's page management, and the Views themselves change in almost every commit (f1bbae77f7, 96434d1c40, e137971afc).

**Timeline:**

- `b3ae88d60f`: MainWindow (root) depends on all Views, which in turn depend on Core, Controls, LiveTranslation, LocalPlayback and the root
- `f1bbae77f7`: MainWindow expanded (+207 lines) together with large rewrites of PlayerView, DetailView, HomeView and SettingsView
- `e137971afc`: MainWindow's navigation reworked around SectionNavigationState, and the Views changed again (DetailView, HomeView, LiveView, LocalVideoView)

**Why it is a problem:** The root namespace holds services that Controls and LocalPlayback rely on, but it also hard-wires the concrete, constantly changing page classes through MainWindow.CreateView. Every page rewrite, which happens in nearly every release here, can force changes in the shell that the rest of the app depends on.

## 6. Unstable Dependency in OrionTV.Desktop.App.LocalPlayback (OrionTV.Desktop.App)

**Designite:** The tool detected the smell in this component because this component depends on other components that are less stable than itself. This component depends on following less stable component(s): OrionTV.Desktop.App

**Classes:** OrionTV.Desktop.App.LocalPlayback.PlaybackState

**Commits that changed its files:** 2

**Emerged in:** b3ae88d60f 2026-07-22

**How:** LocalPlayback's only outgoing project dependency has been the root OrionTV.Desktop.App namespace, and that is the edge the smell flags. MpvLocalEngine uses the PlaybackState enum that is declared in PlaybackController.cs; Designite attributes the participating class to that file. The edge is present in the initial import b3ae88d60f (`private PlaybackState _state = PlaybackState.Idle;`). The root namespace in turn depends on Core and Views, so its own instability is relatively high. The namespace-level dependency structure is the same at the analyzed version as in b3ae88d60f, so the smell is dated to that import; this is an inference from that unchanged structure. Commits e1991e7308, f1bbae77f7 and 96434d1c40 each extended MpvLocalEngine's state machine on top of App's PlaybackState and kept the dependency in place. f1bbae77f7 also changed PlaybackController.cs, where the enum lives.

**Timeline:**

- `b3ae88d60f`: MpvLocalEngine is introduced, storing and raising App's PlaybackState enum
- `e1991e7308`: MpvLocalEngine reworked (+293 lines) and still reports PlaybackState
- `f1bbae77f7`: PlaybackController.cs (which defines PlaybackState) and MpvLocalEngine both modified
- `96434d1c40`: MpvLocalEngine extended further and still coupled to the root's PlaybackState

**Why it is a problem:** The self-contained mpv engine depends on the most volatile part of the app (the root namespace that also holds MainWindow and dozens of services) only to reuse a five-value enum. A change made for the LibVLC PlaybackController can force recompiling and re-testing the local-playback back-end. A shared playback-state abstraction in a stable place would remove this coupling.

_Cites commits that did not change its files: 96434d1c40, e1991e7308_

## 7. Feature Concentration in OrionTV.Desktop.App.Views (OrionTV.Desktop.App)

**Designite:** The tool detected the smell in this component because the component realizes more than one architectural concern/feature. Independent sets of related classes within this component are: [AiImportDialog]' [DetailView]' [FavoritesView]' [HomeView]' [LiveView]' [LocalVideoView' ActiveJobItem' LocalCacheItem' LocalMediaCardItem]' [PlayerShortcutCommand' PlayerShortcutMap' PlayerView' LoadingNoticeMode' PlayerSourceSwitchPolicy' PlayerEpisodeAdvancePolicy]' [SearchView]' [SettingsView]. LCC (Lack of Component Cohesion) = 0'53

**Classes:** OrionTV.Desktop.App.Views.AiImportDialog; OrionTV.Desktop.App.Views.DetailView; OrionTV.Desktop.App.Views.FavoritesView; OrionTV.Desktop.App.Views.HomeView; OrionTV.Desktop.App.Views.LiveView; OrionTV.Desktop.App.Views.LocalVideoView; OrionTV.Desktop.App.Views.ActiveJobItem; OrionTV.Desktop.App.Views.LocalCacheItem; OrionTV.Desktop.App.Views.LocalMediaCardItem; OrionTV.Desktop.App.Views.PlayerShortcutCommand; OrionTV.Desktop.App.Views.PlayerShortcutMap; OrionTV.Desktop.App.Views.PlayerSourceSwitchPolicy; OrionTV.Desktop.App.Views.PlayerEpisodeAdvancePolicy; OrionTV.Desktop.App.Views.PlayerView; OrionTV.Desktop.App.Views.LoadingNoticeMode; OrionTV.Desktop.App.Views.SearchView; OrionTV.Desktop.App.Views.SettingsView

**Commits that changed its files:** 8

**Emerged in:** b3ae88d60f 2026-07-22

**How:** The Views namespace was created in the initial import b3ae88d60f with nine page classes: AiImportDialog, DetailView, FavoritesView, HomeView, LiveView, LocalVideoView (with nested ActiveJobItem and LocalCacheItem), PlayerView (with LoadingNoticeMode), SearchView and SettingsView. None of them reference each other; they only meet through the IAppHost navigation in the root namespace. So the component already consisted of independent groups for AI import, catalog, favorites, live TV, local video, playback, search and settings. fe42a7f077 added LocalMediaCardItem to LocalVideoView. f1bbae77f7 added PlayerShortcutCommand, PlayerShortcutMap, PlayerSourceSwitchPolicy and PlayerEpisodeAdvancePolicy as top-level types inside PlayerView.xaml.cs, which put more feature logic into the views namespace. e137971afc changed LocalVideoView, HomeView, DetailView and LiveView substantially again.

**Timeline:**

- `b3ae88d60f`: Nine unrelated page classes created in the Views namespace
- `fe42a7f077`: LocalVideoView gains a local media library and the LocalMediaCardItem type
- `f1bbae77f7`: Player shortcut and source-switch/episode-advance policy types added inside PlayerView.xaml.cs
- `e137971afc`: Large further changes to LocalVideoView, HomeView, DetailView and LiveView

**Why it is a problem:** Each page is a separate feature with large code-behind (PlayerView is well over 1,000 lines), and policy logic such as source switching and episode advancing lives inside the view files. Changes to live TV, local media, AI import or settings all land in the same namespace. The LCC of 0.53 confirms there is no shared purpose apart from being WPF pages.

## 8. Scattered Functionality in OrionTV.Desktop.App.Views (OrionTV.Desktop.App)

**Designite:** The tool detected the smell in this component because a set of two or more components realizes the same high-level architectural concern. Following components realize the same concern: OrionTV.Desktop.App' OrionTV.Desktop.Core

**Classes:** OrionTV.Desktop.App.ImageLoader; OrionTV.Desktop.Core.FavoriteStore; OrionTV.Desktop.App.AppServices; OrionTV.Desktop.Core.IVodSourceClient; OrionTV.Desktop.Core.VodSourceClientFactory; OrionTV.Desktop.Core.PlayRecordStore; OrionTV.Desktop.Core.PlaybackResumePolicy; OrionTV.Desktop.App.IAppHost; OrionTV.Desktop.Core.LocalMediaStore; OrionTV.Desktop.App.LocalCachePlaybackCatalog; OrionTV.Desktop.App.VodCacheService; OrionTV.Desktop.Core.LocalMediaNaming; OrionTV.Desktop.Core.EpisodeLabelFormatter; OrionTV.Desktop.App.OsdController; OrionTV.Desktop.Core.DesktopLiveSourceSettings; OrionTV.Desktop.Core.M3uParser; OrionTV.Desktop.App.VodDownloadManager; OrionTV.Desktop.Core.CatalogService; OrionTV.Desktop.Core.SearchResultSources; OrionTV.Desktop.App.VodSourceHealthProbe; OrionTV.Desktop.App.VodSourceHealthDisplay

**Commits that changed its files:** 7

**Emerged in:** b3ae88d60f 2026-07-22

**How:** From the first commit b3ae88d60f, the Views implemented the catalog, favorites, history and live-source concern by combining App-side helpers (AppServices, IAppHost, ImageLoader, VodCacheService, VodDownloadManager, OsdController) with Core types (CatalogService, FavoriteStore, PlayRecordStore, IVodSourceClient, VodSourceClientFactory, M3uParser, DesktopLiveSourceSettings, SearchResultSources). So this media-catalog/playback-history concern was split between OrionTV.Desktop.App and OrionTV.Desktop.Core from the start. fe42a7f077 added LocalMediaStore and LocalMediaNaming to Core for the local media library. f1bbae77f7 added PlaybackResumePolicy and EpisodeLabelFormatter to Core, and VodSourceHealthProbe/VodSourceHealthDisplay to App, which DetailView and PlayerView use. e137971afc added LocalCachePlaybackCatalog to App, which HomeView and LocalVideoView use together with Core's LocalMediaNaming and EpisodeLabelFormatter. That completes the reported set of classes.

**Timeline:**

- `b3ae88d60f`: Concern split across App (AppServices, IAppHost, ImageLoader, VodCacheService, VodDownloadManager, OsdController) and Core (CatalogService, FavoriteStore, PlayRecordStore, VodSourceClientFactory, M3uParser, DesktopLiveSourceSettings, SearchResultSources)
- `fe42a7f077`: Core gains LocalMediaStore/LocalMediaNaming for the local media library, used by the views
- `f1bbae77f7`: Core gains PlaybackResumePolicy and EpisodeLabelFormatter; App gains VodSourceHealthProbe/VodSourceHealthDisplay
- `e137971afc`: App gains LocalCachePlaybackCatalog, which HomeView/LocalVideoView combine with Core naming and label helpers

**Why it is a problem:** Episode matching, resume logic and cache lookup are split. Part of it is in the testable Core library (EpisodeLabelFormatter, PlaybackResumePolicy, LocalMediaNaming) and part is in the WPF app namespace (LocalCachePlaybackCatalog, VodSourceHealthDisplay, VodCacheService). As a result, a change in how episodes or history are resolved requires coordinated edits in both components and in several views.

## 9. Scattered Functionality in OrionTV.Desktop.App.Views (OrionTV.Desktop.App)

**Designite:** The tool detected the smell in this component because a set of two or more components realizes the same high-level architectural concern. Following components realize the same concern: OrionTV.Desktop.App.Controls' OrionTV.Desktop.Core

**Classes:** OrionTV.Desktop.App.Controls.CardGrid; OrionTV.Desktop.Core.CatalogService; OrionTV.Desktop.Core.CatalogPlayabilityCache

**Commits that changed its files:** 1

**Emerged in:** b3ae88d60f 2026-07-22

**How:** This was present in the initial import b3ae88d60f. CardGrid (OrionTV.Desktop.App.Controls) displays and replaces CatalogItem cards. The Core types CatalogService and CatalogPlayabilityCache (exposed through AppServices.Catalog and AppServices.PlayabilityCache) fetch the catalog and cache playability. HomeView, SearchView and FavoritesView combine the two: HomeView calls Services.Catalog.GetHomeDataAsync, checks Services.PlayabilityCache, and then updates its CardGrid. So the 'catalog grid browsing' concern is spread over Controls and Core. The relevant parts of CardGrid did not change structurally afterwards. f1bbae77f7 extended CatalogService and CatalogModels.cs (where CatalogPlayabilityCache lives), and e137971afc changed HomeView's use of them, which kept the concern spread out.

**Timeline:**

- `b3ae88d60f`: CardGrid (Controls) and CatalogService/CatalogPlayabilityCache (Core) both realise catalog browsing, wired together in HomeView/SearchView
- `f1bbae77f7`: CatalogService and CatalogModels (CatalogPlayabilityCache) extended

**Why it is a problem:** Showing a playable catalog grid needs the control's item replacement (ReplaceItem), Core's playability cache and its generation counter, and the coordinating view. A change to how playability is shown or cached therefore has to stay consistent across Controls, Core and every page that hosts a CardGrid.

_Cites commits that did not change its files: f1bbae77f7_

## 10. Scattered Functionality in OrionTV.Desktop.App.Views (OrionTV.Desktop.App)

**Designite:** The tool detected the smell in this component because a set of two or more components realizes the same high-level architectural concern. Following components realize the same concern: OrionTV.Desktop.App' OrionTV.Desktop.App.LiveTranslation

**Classes:** OrionTV.Desktop.App.PlaybackController; OrionTV.Desktop.App.LiveTranslation.LiveTranslationController; OrionTV.Desktop.App.IAppHost; OrionTV.Desktop.App.AppServices

**Commits that changed its files:** 5

**Emerged in:** b3ae88d60f 2026-07-22

**How:** This was present in the initial import b3ae88d60f. LiveView creates a LibVLC PlaybackController from the root namespace (`new PlaybackController(_host.Services.LibVlc, Dispatcher)`, using AppServices via IAppHost). It also creates a LiveTranslationController from OrionTV.Desktop.App.LiveTranslation, which taps the same audio through LibVlcAudioTap. The live playback-with-translation concern is therefore split between the root namespace and LiveTranslation, and LiveView ties them together. f1bbae77f7 extended PlaybackController (+110 lines), AppServices and Navigation, and e137971afc changed LiveView again (+115 lines) and Navigation, keeping the split.

**Timeline:**

- `b3ae88d60f`: PlaybackController/AppServices/IAppHost (root) and LiveTranslationController (LiveTranslation) together realise live playback with translation
- `f1bbae77f7`: PlaybackController, AppServices and Navigation extended
- `e137971afc`: LiveView and Navigation (IAppHost area) changed again

**Why it is a problem:** Live-translated playback needs the LibVLC controller and LibVLC instance from the root namespace and the translation pipeline from LiveTranslation, coordinated by hand in LiveView. Changing how audio is captured or how playback state works means editing two namespaces plus the view. Neither part can be reused on its own.

## 11. Scattered Functionality in OrionTV.Desktop.App.Views (OrionTV.Desktop.App)

**Designite:** The tool detected the smell in this component because a set of two or more components realizes the same high-level architectural concern. Following components realize the same concern: OrionTV.Desktop.Core' OrionTV.Desktop.App.LiveTranslation

**Classes:** OrionTV.Desktop.Core.GeminiLiveTranslateProtocol; OrionTV.Desktop.App.LiveTranslation.OpenAiCredentialStore; OrionTV.Desktop.Core.RollingSubtitleBuffer; OrionTV.Desktop.App.LiveTranslation.LiveTranslationController

**Commits that changed its files:** 1

**Emerged in:** b3ae88d60f 2026-07-22

**How:** This was present in the initial import b3ae88d60f. The live translation concern is split between Core (GeminiLiveTranslateProtocol, and RollingSubtitleBuffer in RealtimeTranslationProtocol.cs) and App.LiveTranslation (LiveTranslationController, OpenAiCredentialStore, plus the clients). The views drive it from both sides: LiveView reads API keys via OpenAiCredentialStore.ReadApiKeyForProvider and creates LiveTranslationController, and SettingsView saves and deletes keys through OpenAiCredentialStore. None of the participating files changed structurally in later commits. The only later change found is the string rename in 0c5495360e, which did not affect the split.

**Timeline:**

- `b3ae88d60f`: Translation protocol/subtitle buffering placed in Core, while controller and credential storage are in App.LiveTranslation; LiveView and SettingsView use both

**Why it is a problem:** Protocol framing and subtitle buffering live in Core, but the session controller and credential storage live in the WPF project. Adding or changing a translation provider means touching Core, LiveTranslation, LiveView and SettingsView together.

## 12. Scattered Functionality in OrionTV.Desktop.App.Views (OrionTV.Desktop.App)

**Designite:** The tool detected the smell in this component because a set of two or more components realizes the same high-level architectural concern. Following components realize the same concern: OrionTV.Desktop.App.LocalPlayback' OrionTV.Desktop.App

**Classes:** OrionTV.Desktop.App.LocalPlayback.MpvHost; OrionTV.Desktop.App.PlaybackController; OrionTV.Desktop.App.LocalPlayback.MpvLocalEngine; OrionTV.Desktop.App.IAppHost; OrionTV.Desktop.App.AppServices

**Commits that changed its files:** 7

**Emerged in:** b3ae88d60f 2026-07-22

**How:** This was present in the initial import b3ae88d60f. Video playback is implemented twice: by PlaybackController (LibVLC) in the root namespace, reached through AppServices/IAppHost, and by MpvHost plus MpvLocalEngine in OrionTV.Desktop.App.LocalPlayback. PlayerView hosts both (an MpvHost in XAML, `new PlaybackController(libVlc, Dispatcher)` and `new MpvLocalEngine(hwnd, Dispatcher)`). Later commits kept growing both sides in parallel. fe42a7f077 changed MpvHost and MpvLocalEngine for local media playback. e1991e7308 extended MpvHost (+77 lines) and MpvLocalEngine (+293 lines). f1bbae77f7 extended both PlaybackController (+110 lines) and MpvLocalEngine (+153 lines) as well as AppServices and Navigation, and 96434d1c40 extended MpvLocalEngine again.

**Timeline:**

- `b3ae88d60f`: LibVLC PlaybackController (root) and MpvHost/MpvLocalEngine (LocalPlayback) both implement playback, combined in PlayerView
- `fe42a7f077`: MpvHost/MpvLocalEngine adapted for local media library playback
- `e1991e7308`: MpvHost and MpvLocalEngine extended to keep mpv controls aligned with the player UI
- `f1bbae77f7`: PlaybackController, MpvLocalEngine, AppServices and Navigation all extended
- `96434d1c40`: MpvLocalEngine extended further

**Why it is a problem:** The two playback engines live in different namespaces and share no common interface, only the PlaybackState enum. PlayerView must branch between them. Each playback feature (seeking, state, controls) has to be implemented and kept consistent in both places, as the paired changes across these commits show.

## 13. God Component in OrionTV.Desktop.Core (OrionTV.Desktop.Core)

**Designite:** The tool detected the smell in this component because the component contains high number of classes. Number of classes in the component are: 56

**Classes:** OrionTV.Desktop.Core.AppleCmsUrlBuilder; OrionTV.Desktop.Core.AppleCmsEpisodeParser; OrionTV.Desktop.Core.SearchResultSources; OrionTV.Desktop.Core.AppleCmsMapper; OrionTV.Desktop.Core.AppleCmsClient; OrionTV.Desktop.Core.CatalogPlayabilityStatus; OrionTV.Desktop.Core.CatalogTitleMatcher; OrionTV.Desktop.Core.CatalogPlayabilityBadge; OrionTV.Desktop.Core.CatalogPlayabilityCache; OrionTV.Desktop.Core.PlaybackResumePolicy; OrionTV.Desktop.Core.PlaybackFallbackSelector; OrionTV.Desktop.Core.PlaybackMediaOptions; OrionTV.Desktop.Core.PlaybackStartupWatchdog; OrionTV.Desktop.Core.PlaybackStartupSignal; OrionTV.Desktop.Core.PlaybackStartupPolicy; OrionTV.Desktop.Core.CatalogService; OrionTV.Desktop.Core.ChannelHealth; OrionTV.Desktop.Core.MediaProbeStatus; OrionTV.Desktop.Core.ChannelHealthScoring; OrionTV.Desktop.Core.ChannelHealthDisplay; OrionTV.Desktop.Core.ChannelHealthProbe; OrionTV.Desktop.Core.DeepgramSttProtocol; OrionTV.Desktop.Core.DesktopLiveSourceSettings; OrionTV.Desktop.Core.DoubanClient; OrionTV.Desktop.Core.DoubaoAstProtocol; OrionTV.Desktop.Core.ExtraVideoSourcesStore; OrionTV.Desktop.Core.VideoSourceMerger; OrionTV.Desktop.Core.AiImportPromptBuilder; OrionTV.Desktop.Core.GeminiLiveTranslateProtocol; OrionTV.Desktop.Core.HlsAdSkip; OrionTV.Desktop.Core.HomeCategoryMatcher; OrionTV.Desktop.Core.IVodSourceClient; OrionTV.Desktop.Core.VodSourceClientFactory; OrionTV.Desktop.Core.UnsupportedVodSourceClient; OrionTV.Desktop.Core.LocalMediaNaming; OrionTV.Desktop.Core.NaturalPathComparer; OrionTV.Desktop.Core.LocalMediaStore; OrionTV.Desktop.Core.JsonDictionaryStore<T>; OrionTV.Desktop.Core.FavoriteStore; OrionTV.Desktop.Core.PlayRecordStore; OrionTV.Desktop.Core.M3uParser; OrionTV.Desktop.Core.MacCmsJsonClient; OrionTV.Desktop.Core.MacCmsXmlClient; OrionTV.Desktop.Core.VideoSourceProtocols; OrionTV.Desktop.Core.EpisodeLabelFormatter; OrionTV.Desktop.Core.AppleCmsVodItem; OrionTV.Desktop.Core.RealtimeTranslationEventKind; OrionTV.Desktop.Core.RealtimeTranslationProtocol; OrionTV.Desktop.Core.Pcm16TranslationFrameBuffer; OrionTV.Desktop.Core.RollingSubtitleBuffer; OrionTV.Desktop.Core.DesktopPaths; OrionTV.Desktop.Core.VodCacheSettings; OrionTV.Desktop.Core.DesktopSettingsMigration; OrionTV.Desktop.Core.DesktopSettingsForm; OrionTV.Desktop.Core.SettingsStore; OrionTV.Desktop.Core.VideoSourceSubscriptionParser

**Commits that changed its files:** 5

**Emerged in:** b3ae88d60f 2026-07-22

**How:** The smell was already there in the first commit of the desktop Core project. Commit b3ae88d60f ("feat: publish source-free OrionTV") added OrionTV.Desktop.Core as a single import with 51 class, interface and enum types, which is far above Designite's class-count threshold. That import already mixed many unrelated concerns:
- clients for the Apple CMS and MacCMS (JSON and XML) video-source APIs (AppleCms.cs, MacCmsJsonClient, MacCmsXmlClient, IVodSourceClient/VodSourceClientFactory/UnsupportedVodSourceClient);
- the Douban client;
- catalog and playback policies (CatalogModels.cs with CatalogPlayabilityCache, PlaybackStartupWatchdog/Policy, PlaybackFallbackSelector, PlaybackMediaOptions) and CatalogService;
- live-channel health probing (ChannelHealthProbe.cs);
- the M3U parser and HLS ad skipping;
- real-time translation and speech-to-text protocols (Deepgram, Doubao, Gemini, RealtimeTranslationProtocol and its buffers);
- JSON persistence stores (LocalStore.cs);
- settings and paths (Settings.cs);
- source subscriptions and merging (ExtraVideoSources.cs, VideoSourceSubscriptionParser).

Neither 0c5495360e (rename) nor 4a7b4a2362 (version bump) touched Core. Two later commits made it worse:
- fe42a7f077 ("add local media library playback") added LocalMediaLibrary.cs with LocalMediaNaming and LocalMediaStore, bringing the count to 53.
- f1bbae77f7 ("prepare desktop 1.3.15 release") added PlaybackResumePolicy to CatalogModels.cs, the MediaProbeStatus enum to ChannelHealthProbe.cs (which grew by about 527 lines) and EpisodeLabelFormatter to Models.cs, bringing the count to 56.

The next two commits kept the smell alive without adding classes. 96434d1c40 only bumped the Core csproj. e137971afc grew LocalStore.cs (PlayRecordStore history logic) but added no new types.

**Timeline:**

- `b3ae88d60f`: Initial import of OrionTV.Desktop.Core with 51 types covering VOD API clients, Douban, catalog and playback policies, channel health probing, M3U/HLS handling, AI translation protocols, local stores and settings. The God Component is already present.
- `fe42a7f077`: Added LocalMediaLibrary.cs (LocalMediaNaming, LocalMediaStore) and extended LocalStore.cs and Settings.cs, giving the component a local media library responsibility (53 types).
- `f1bbae77f7`: Added PlaybackResumePolicy, the MediaProbeStatus enum and EpisodeLabelFormatter, and greatly expanded ChannelHealthProbe.cs, CatalogModels.cs and AppleCms.cs (56 types).
- `e137971afc`: Extended LocalStore.cs with play-record history logic, adding more to the component without splitting it.

**Why it is a problem:** OrionTV.Desktop.Core is a single catch-all assembly that holds HTTP clients for several VOD protocols, Douban metadata, live-stream health probing, HLS ad skipping, protocols for three different AI translation and speech-to-text vendors, playback startup and resume policies, and JSON file persistence. These concerns have nothing to do with each other. Any change, such as a Gemini protocol tweak or a new MacCMS field, touches and rebuilds the same component that the WPF app depends on everywhere. The component cannot be reused in parts (for example, only the source clients), and with 56 types and no sub-namespaces it is hard to see where a responsibility lives.

## 14. Feature Concentration in OrionTV.Desktop.Tests (OrionTV.Desktop.Tests)

**Designite:** The tool detected the smell in this component because the component realizes more than one architectural concern/feature. Independent sets of related classes within this component are: [AiCliLauncherTests]' [AppleCmsServiceTests' StubHandler' VodProtocolTests]' [ChannelHealthScoringTests' RecordingHandler' FlvResponseHandler' HtmlResponseHandler' MisleadingHtmlResponseHandler' EncryptedHlsHandler' HtmlSegmentHandler' VariantRecordingHandler]' [DesktopSettingsTests]' [LocalStoreTests' TestStringStore]' [DesktopUpdateServiceTests' StubHttpMessageHandler' InlineProgress]' [ExtraVideoSourcesTests]' [HlsAdSkipTests]' [HomeCategoryMatcherTests]' [LocalCachePlaybackCatalogTests]' [LocalMediaLibraryTests]' [M3uParserTests]' [MpvLocalEngineTests]' [PlaybackResumePolicyTests]' [WpfNavigationCollection' PlayerNavigationSurfaceTests]' [PlayerShortcutTests]' [PlayRecordHistoryTests]' [RealtimeTranslationProtocolTests]' [GeminiLiveTranslateProtocolTests]' [DeepgramSttProtocolTests]' [DoubaoAstProtocolTests]' [SubscriptionParserTests]' [VodCacheLookupTests]' [VodCacheServiceTests' InlineProgress<T>' BlockingFirstProgress' FakeHlsServer]' [VodSourceHealthProbeTests' StubDecodeProbe]. LCC (Lack of Component Cohesion) = 0'6

**Classes:** OrionTV.Desktop.Tests.AiCliLauncherTests; OrionTV.Desktop.Tests.AppleCmsServiceTests; OrionTV.Desktop.Tests.StubHandler; OrionTV.Desktop.Tests.ChannelHealthScoringTests; OrionTV.Desktop.Tests.RecordingHandler; OrionTV.Desktop.Tests.FlvResponseHandler; OrionTV.Desktop.Tests.HtmlResponseHandler; OrionTV.Desktop.Tests.MisleadingHtmlResponseHandler; OrionTV.Desktop.Tests.EncryptedHlsHandler; OrionTV.Desktop.Tests.HtmlSegmentHandler; OrionTV.Desktop.Tests.VariantRecordingHandler; OrionTV.Desktop.Tests.DesktopSettingsTests; OrionTV.Desktop.Tests.LocalStoreTests; OrionTV.Desktop.Tests.TestStringStore; OrionTV.Desktop.Tests.DesktopUpdateServiceTests; OrionTV.Desktop.Tests.StubHttpMessageHandler; OrionTV.Desktop.Tests.InlineProgress; OrionTV.Desktop.Tests.ExtraVideoSourcesTests; OrionTV.Desktop.Tests.HlsAdSkipTests; OrionTV.Desktop.Tests.HomeCategoryMatcherTests; OrionTV.Desktop.Tests.LocalCachePlaybackCatalogTests; OrionTV.Desktop.Tests.LocalMediaLibraryTests; OrionTV.Desktop.Tests.M3uParserTests; OrionTV.Desktop.Tests.MpvLocalEngineTests; OrionTV.Desktop.Tests.PlaybackResumePolicyTests; OrionTV.Desktop.Tests.WpfNavigationCollection; OrionTV.Desktop.Tests.PlayerNavigationSurfaceTests; OrionTV.Desktop.Tests.PlayerShortcutTests; OrionTV.Desktop.Tests.PlayRecordHistoryTests; OrionTV.Desktop.Tests.RealtimeTranslationProtocolTests; OrionTV.Desktop.Tests.GeminiLiveTranslateProtocolTests; OrionTV.Desktop.Tests.DeepgramSttProtocolTests; OrionTV.Desktop.Tests.DoubaoAstProtocolTests; OrionTV.Desktop.Tests.SubscriptionParserTests; OrionTV.Desktop.Tests.VodCacheLookupTests; OrionTV.Desktop.Tests.VodCacheServiceTests; OrionTV.Desktop.Tests.InlineProgress<T>; OrionTV.Desktop.Tests.BlockingFirstProgress; OrionTV.Desktop.Tests.FakeHlsServer; OrionTV.Desktop.Tests.VodProtocolTests; OrionTV.Desktop.Tests.VodSourceHealthProbeTests; OrionTV.Desktop.Tests.StubDecodeProbe

**Commits that changed its files:** 9

**Emerged in:** b3ae88d60f 2026-07-22

**How:** 1) b3ae88d60f ("feat: publish source-free OrionTV") created the whole test project in one import, with 12 test files covering unrelated parts of the product: AI CLI launcher (AiCliLauncherTests), AppleCMS catalog (AppleCmsServiceTests + StubHandler), live channel health scoring (ChannelHealthScoringTests + RecordingHandler/FlvResponseHandler), settings and local stores (DesktopSettingsTests, LocalStoreTests, TestStringStore), extra sources, HLS ad skipping, home category matching, M3U parsing, four realtime-translation protocol test classes, subscription parsing, VOD caching (VodCacheServiceTests + FakeHlsServer) and VOD protocol (VodProtocolTests + StubHandler). These test classes do not use each other. They split into many disconnected groups, so the component already showed low cohesion and met the Feature Concentration definition in this first commit.
2) After that, each feature commit added another unrelated group: fe42a7f077 added LocalMediaLibraryTests; 61f0607246 added MpvLocalEngineTests; f1bbae77f7 added DesktopUpdateServiceTests (+StubHttpMessageHandler, InlineProgress), PlaybackResumePolicyTests, PlayerShortcutTests, VodCacheLookupTests and VodSourceHealthProbeTests (+StubDecodeProbe), plus five new HTTP stub handlers in ChannelHealthScoringTests; c601eb789d added PlayerNavigationSurfaceTests with WpfNavigationCollection; e137971afc added LocalCachePlaybackCatalogTests, PlayRecordHistoryTests and the InlineProgress<T>/BlockingFirstProgress helpers in VodCacheServiceTests. This produced the 27 independent groups reported (LCC 0.6).

**Timeline:**

- `b3ae88d60f`: Initial import puts tests for about 12 unrelated features (AI CLI, AppleCMS, channel health, settings/store, M3U, translation protocols, VOD cache/protocol, etc.) into one project
- `fe42a7f077`: Adds LocalMediaLibraryTests, a new independent group
- `61f0607246`: Adds MpvLocalEngineTests, a new independent group
- `f1bbae77f7`: Adds DesktopUpdateServiceTests, PlaybackResumePolicyTests, PlayerShortcutTests, VodCacheLookupTests, VodSourceHealthProbeTests and their helper stubs; adds five more stub handlers to ChannelHealthScoringTests
- `c601eb789d`: Adds PlayerNavigationSurfaceTests and WpfNavigationCollection
- `e137971afc`: Adds LocalCachePlaybackCatalogTests, PlayRecordHistoryTests and the InlineProgress<T>/BlockingFirstProgress helpers

**Why it is a problem:** One test assembly checks the AI CLI launcher, update installer, mpv engine, WPF navigation, live-channel probing, four cloud-translation protocols and the VOD cache all together. A change in any one subsystem rebuilds and reruns tests for all the others, and slow or Windows-only tests (PowerShell process launches, fake HLS servers) are mixed with pure parser tests. The many separate private HttpMessageHandler/IProgress stubs (StubHandler twice, StubHttpMessageHandler, RecordingHandler, InlineProgress and InlineProgress<T>) show that there is no shared test infrastructure per feature, so the code is duplicated instead.

## 15. God Component in OrionTV.Desktop.Tests (OrionTV.Desktop.Tests)

**Designite:** The tool detected the smell in this component because the component contains high number of classes. Number of classes in the component are: 42

**Classes:** OrionTV.Desktop.Tests.AiCliLauncherTests; OrionTV.Desktop.Tests.AppleCmsServiceTests; OrionTV.Desktop.Tests.StubHandler; OrionTV.Desktop.Tests.ChannelHealthScoringTests; OrionTV.Desktop.Tests.RecordingHandler; OrionTV.Desktop.Tests.FlvResponseHandler; OrionTV.Desktop.Tests.HtmlResponseHandler; OrionTV.Desktop.Tests.MisleadingHtmlResponseHandler; OrionTV.Desktop.Tests.EncryptedHlsHandler; OrionTV.Desktop.Tests.HtmlSegmentHandler; OrionTV.Desktop.Tests.VariantRecordingHandler; OrionTV.Desktop.Tests.DesktopSettingsTests; OrionTV.Desktop.Tests.LocalStoreTests; OrionTV.Desktop.Tests.TestStringStore; OrionTV.Desktop.Tests.DesktopUpdateServiceTests; OrionTV.Desktop.Tests.StubHttpMessageHandler; OrionTV.Desktop.Tests.InlineProgress; OrionTV.Desktop.Tests.ExtraVideoSourcesTests; OrionTV.Desktop.Tests.HlsAdSkipTests; OrionTV.Desktop.Tests.HomeCategoryMatcherTests; OrionTV.Desktop.Tests.LocalCachePlaybackCatalogTests; OrionTV.Desktop.Tests.LocalMediaLibraryTests; OrionTV.Desktop.Tests.M3uParserTests; OrionTV.Desktop.Tests.MpvLocalEngineTests; OrionTV.Desktop.Tests.PlaybackResumePolicyTests; OrionTV.Desktop.Tests.WpfNavigationCollection; OrionTV.Desktop.Tests.PlayerNavigationSurfaceTests; OrionTV.Desktop.Tests.PlayerShortcutTests; OrionTV.Desktop.Tests.PlayRecordHistoryTests; OrionTV.Desktop.Tests.RealtimeTranslationProtocolTests; OrionTV.Desktop.Tests.GeminiLiveTranslateProtocolTests; OrionTV.Desktop.Tests.DeepgramSttProtocolTests; OrionTV.Desktop.Tests.DoubaoAstProtocolTests; OrionTV.Desktop.Tests.SubscriptionParserTests; OrionTV.Desktop.Tests.VodCacheLookupTests; OrionTV.Desktop.Tests.VodCacheServiceTests; OrionTV.Desktop.Tests.InlineProgress<T>; OrionTV.Desktop.Tests.BlockingFirstProgress; OrionTV.Desktop.Tests.FakeHlsServer; OrionTV.Desktop.Tests.VodProtocolTests; OrionTV.Desktop.Tests.VodSourceHealthProbeTests; OrionTV.Desktop.Tests.StubDecodeProbe

**Commits that changed its files:** 9

**Emerged in:** f1bbae77f7 2026-07-27

**How:** 1) b3ae88d60f created the project with about 20 distinctly named classes (test classes plus nested stubs such as StubHandler, RecordingHandler, FlvResponseHandler, TestStringStore, FakeHlsServer), which is below a God Component class-count threshold.
2) fe42a7f077 (LocalMediaLibraryTests) and 61f0607246 (MpvLocalEngineTests) each added one class, bringing the count to about 22.
3) f1bbae77f7 ("prepare desktop 1.3.15 release") added 13 classes at once: DesktopUpdateServiceTests, StubHttpMessageHandler, InlineProgress, PlaybackResumePolicyTests, PlayerShortcutTests, VodCacheLookupTests, VodSourceHealthProbeTests, StubDecodeProbe, and HtmlResponseHandler, MisleadingHtmlResponseHandler, EncryptedHlsHandler, HtmlSegmentHandler and VariantRecordingHandler inside ChannelHealthScoringTests. This took the count to about 35, past the usual threshold, so this is the commit where the smell appeared.
4) c601eb789d added WpfNavigationCollection and PlayerNavigationSurfaceTests (about 37 classes).
5) e137971afc added LocalCachePlaybackCatalogTests, PlayRecordHistoryTests, InlineProgress<T> and BlockingFirstProgress, reaching the 42 classes reported.

**Timeline:**

- `b3ae88d60f`: Creates the test project with about 20 classes in 12 files
- `fe42a7f077`: Adds LocalMediaLibraryTests
- `61f0607246`: Adds MpvLocalEngineTests
- `f1bbae77f7`: Adds 13 classes (5 new test classes plus 8 stubs/handlers), crossing the class-count threshold
- `c601eb789d`: Adds PlayerNavigationSurfaceTests and WpfNavigationCollection
- `e137971afc`: Adds LocalCachePlaybackCatalogTests, PlayRecordHistoryTests, InlineProgress<T> and BlockingFirstProgress (42 classes)

**Why it is a problem:** The single OrionTV.Desktop.Tests project has become the place where every release commit (1.3.15, 1.3.16, 1.3.17) puts its tests, so it grows with each feature and has no internal structure: all 22 files sit flat in one namespace. Large files such as VodCacheServiceTests (over 880 lines with three nested helpers) and ChannelHealthScoringTests (seven nested handlers) make it hard to find, maintain and selectively run the tests for one subsystem. The test project also depends on both App and Core, so most changes anywhere in the product touch it.
