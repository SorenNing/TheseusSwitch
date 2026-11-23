# Link interface provenance

`libroothide.tbd` is a checked-in **link-time interface only**, not an implementation and never packaged. Runtime implementation comes from `Depends: roothide (>= 0.0.1)`.

Authoritative upstream: https://github.com/roothide/libroothide/tree/cb236f9cf1c5e2ac932611328998a62b4b133e33

- `Makefile` target `libroothide.dylib`: `-install_name @loader_path/.jbroot/usr/lib/libroothide.dylib`.
- `roothide.h`: C exports rootfs_alloc, jbroot_alloc, jbrootat_alloc, jbrand, jbroot, rootfs.
- `control`: package roothide, version 0.0.1, architecture iphoneos-arm64e.
- `roothide.h` is preserved in packaging/include/roothide/ with its MIT license. C exports only are represented in the minimal TBD. Use its const char * interface or an actual devkit when overloads are needed.
- Build uses `-needed-lroothide` so the final Mach-O has a genuine LC_LOAD_DYLIB even if physical resource path resolution makes a direct call unnecessary. Strict verification requires that install name in BOTH RootHide main and preferences Mach-O files, and forbids it in rootless packages. No local fake dylib is produced or shipped.

`Preferences.framework/Preferences.tbd` is the minimal fallback interface for Apple's private framework at `/System/Library/PrivateFrameworks/Preferences.framework/Preferences`. Prefer `THEOS/sdks/iPhoneOS16.5.sdk/System/Library/PrivateFrameworks/Preferences.framework/Preferences.tbd` when supplied. The normal Xcode SDK remains the compile SDK so original sources can use newer SDK declarations behind availability checks. The fallback represents only PSListController, PSSpecifier, PSTableCell and PSViewController Objective-C classes; additional unresolved symbols fail at link time. Link uses `-framework Preferences` and never `-undefined dynamic_lookup`.
