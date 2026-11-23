#import <Foundation/Foundation.h>
#import <UIKit/UIKit.h>

NS_ASSUME_NONNULL_BEGIN
FOUNDATION_EXPORT NSBundle * _Nullable NGBundleResources(void);
FOUNDATION_EXPORT NSArray<NSString *> *NGPreferencePaths(void);
FOUNDATION_EXPORT NSDictionary *NGReadPreferences(void);
FOUNDATION_EXPORT BOOL NGStorePreference(NSString *key, id value);
FOUNDATION_EXPORT void NGPreferencesReload(void);
FOUNDATION_EXPORT BOOL NGSwitchEnabled(void);
FOUNDATION_EXPORT void NGRefreshSwitch(UISwitch *source);
FOUNDATION_EXPORT void NGRefreshAllSwitches(void);
FOUNDATION_EXPORT void NGRemoveSwitch(UISwitch *source);
FOUNDATION_EXPORT void NGSyncSwitch(UISwitch *source, BOOL animated);
FOUNDATION_EXPORT BOOL NGHandleSwitchAlpha(UISwitch *source, CGFloat alpha);
FOUNDATION_EXPORT void NGRefreshAll(void);

@protocol NGSwitchComponent <NSObject>
@property(nonatomic,copy,nullable) void (^onChanged)(BOOL value);
@property(nonatomic,getter=isOn) BOOL on;
- (void)setOn:(BOOL)value animated:(BOOL)animated;
@end
NS_ASSUME_NONNULL_END
