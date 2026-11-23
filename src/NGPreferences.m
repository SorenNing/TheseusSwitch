#import "Bridge.h"

static BOOL gNGSwitchEnabled = YES;

void NGPreferencesReload(void) {
    NSDictionary *data = NGReadPreferences();
    id sw = data[@"enabledSwitch"];
    gNGSwitchEnabled = [sw isKindOfClass:NSNumber.class] ? [sw boolValue] : YES;
}
BOOL NGSwitchEnabled(void) { return gNGSwitchEnabled; }
void NGRefreshAll(void) { NGRefreshAllSwitches(); }
