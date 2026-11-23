# TheseusSwitch — standalone source 0.1.3

仅本地拆分的越狱插件源码，不是已编译安装包，也不是 Theseus 官方发布。

## 来源与完整性

从本地保存的 GlassSwitchDock 稳定优化 0.1.3 归档 `source-25cbb79.tar.gz` 提取：

- 基线提交：`25cbb795c9f0f645c8a933d7e04da88454912320`
- 对应树：`1077bffb9bd4a272041298abaab1b883ec8b60c5`
- Theseus 上游：https://github.com/valzevul/Theseus
- 上游提交：`71ca1c127a4e7fe3387361f160c4890dbd427f66`
- 上游作者：Vadim Drobinin；原插件集成：Ning。

原请求中的 workspace 路径当前不存在，因此使用 shared/glassswitchdock-evidence/restore-stable-013-20261118 中保存的同一基线归档。没有读写远程仓库，没有创建仓库或触发 CI。

`Vendor/Theseus` 完整保留基线分发的 37 个上游原文件及 UPSTREAM.json 元数据，未改动其任何字节。`Vendor/manifest.json` 是原基线 manifest 的 Theseus 子集，而不是对改后源码重新生成的信任声明。LICENSE、NOTICE、源代码署名均保留。为避免修改 Package.swift，TheseusSlider.swift 和 TheseusTabBar.swift 仍归档保留，但明确排除于本插件编译列表；这不是系统 Dock 集成。Vendor/Theseus/Package.swift 仅作为原件保留，不是此插件的构建入口，它的上游 test target 不在基线分发文件范围内。

## 内容与行为

- `src/Tweak.m`：九个 UISwitch Hook，动态解析 MSHookMessageEx；保留继承方法本地化，避免修改 UIView 的方法实现。
- `src/NGSwitch.m`：与 0.1.3 完全一致；63×28 Theseus 原版控件同级覆盖层、值和 enabled 同步、每次逻辑变化一次 valueChanged、回调拒绝值回同步、重挂载、隐藏、alpha 和关闭恢复。
- `src/TheseusBridge.swift`：只保留原开关桥接，不重写 Theseus 材质、颜色、动画、物理或尺寸默认值。
- `src/NGPreferences.m`、`NGResources.m`、`TheseusBundle.swift`、`Bridge.h`：独立设置、资源解析、Swift Bundle.module 桥接。
- `prefs/`：完整 PreferenceLoader 面板、Info/entry/Root plist 和所用 PNG 图标，只保留一个“启用开关”，默认开。
- `Vendor/Theseus/`：原版控件及全部渲染、动画、捕获、fallback 支持；原版 Metal shader 一份。
- `packaging/`：双变体配置、Preferences 最小链接接口、RootHide 链接接口/头文件及许可证、无 respring postinst。
- `tools/`：源检查、原生编译/签名/资源/打包脚本、独立 deb 结构和 Mach-O 验证器。

已移除 NGDock、壁纸捕获适配、Dock Hook、Dock Swift 桥接、Dock 设置和图标、Glassify 全部源码和 shader、Glassify Bundle 访问器。旧混合工程的 CI workflow 和模拟器 Harness 不随本独立工程发货，不能把旧工程测试结果当作新插件验证。

## 独立标识与依赖

名称 TheseusSwitch，包标识/偏好域 `com.ning.theseusswitch`，通知 `com.ning.theseusswitch/changed`，输出 TheseusSwitch.dylib、TheseusSwitchPrefs.bundle、TheseusSwitchResources.bundle。不会复用旧偏好域。为避免双重 UISwitch Hook，与 com.ning.glassswitchdock/com.ning.switch/com.ning.daynightswitch 冲突。

运行依赖：iOS >= 15、PreferenceLoader、提供 MSHookMessageEx 的 mobilesubstrate 兼容实现；arm64e RootHide 额外依赖 roothide >= 0.0.1。SDK 原生 Foundation/UIKit/Metal/MetalKit/QuartzCore/CoreGraphics/CoreVideo/IOSurface/Accelerate 随系统使用，不随源码提供二进制。RootHide TBD 仅链接接口，不打包假库。

安装布局由 packaging/config.json 决定：arm64 rootless 前缀 /var/jb；arm64e RootHide 逻辑前缀为空。资源解析沿用基线 dladdr/realpath 对真实安装前缀的识别方式，偏好读取兼容标准和重定向路径。RootHide 注入、路径映射及 hook engine 仍需真机验证。

## 静态检查与后续构建方法

默认 `make`/`make check` 仅运行 Python 静态检查，不编译、不连接网络。可运行：

```sh
python3 tools/project.py --output evidence/source-check.json
python3 -m py_compile tools/*.py
sh -n packaging/postinst
```

未来只有另行授权后，在 macOS + 完整 Xcode（建议 Xcode 26+，需新版 SDK 声明）和 Python 3.10+ 环境运行：

```sh
make build ARCH=arm64e  # RootHide；不是普通 rootless arm64e 包
make verify ARCH=arm64e
# 可选普通 rootless：make build ARCH=arm64
```

构建脚本用 Xcode swiftc 编译 31 个上游 Swift 支持源和 2 个集成 Swift 源，同模块链接 4 个 Objective-C 核心源；不编译 TheseusSlider/TheseusTabBar。编译一份 TheseusShaders.metal 到唯一 default.metallib；设置面板单独链接 Preferences.framework。保留 Swift 驱动链接计划提取、实际 arm64e CPU subtype 检查、RootHide 显式依赖、原生 codesign、Preference bundle 封装签名、最终 deb 重解包检查。构建过程本身无需下载源码。可用 THEOS 的 iPhoneOS16.5.sdk Preferences TBD；无此路径时使用内置最小 fallback。`--smoke` 仅是模拟器编译模式，不执行 UIKit 测试，亦未在此次执行。

## 已执行验证与限制

此次仅执行源码归档字节校验、37 个上游原件 SHA-256 校验、38 个 Vendor/Theseus 文件与本地稳定基线逐字节对比、plist/JSON 解析、Hook/桥接/资源/设置依赖静态检查、Python 语法及 postinst shell 语法检查、ZIP 内容/CRC 校验。结果见 evidence/。

未执行 Xcode/Swift/ObjC/Metal 原生编译、链接、签名、deb 构建、模拟器运行、注入或真机验证。因此此交付是完整独立源码候选，不能声称已可编译、已安装成功、或真机视觉/交互与原版完全一致。尤其低版本 iOS availability、系统/第三方 UISwitch 子类、辅助功能、变换/裁剪/复用、RootHide 和其它插件冲突、性能及实际材质效果尚待原生和真机测试。保持原版代码和桥接语义不等于完成视觉验收。

## 许可边界

Theseus 适用其未改动的 LICENSE/NOTICE（Apache 2.0）；RootHide 头文件按其自带 LICENSE。集成源码来自 Ning 的上述基线。该基线归档没有单独提供集成层顶级 LICENSE，本交付不擅自替作者授权，也不把上游许可证自动扩展到未声明的集成代码；进一步公开再分发/商业用途应向集成作者确认。保留源码注释和署名，不代表获得额外授权。
