from kivy.app import App
from kivy.lang import Builder
from kivy.uix.screenmanager import ScreenManager, Screen
from kivy.clock import Clock
from kivy.properties import StringProperty, DictProperty
from kivy.factory import Factory

import os
import json
from kivy.utils import platform

from logic_backend import (
    api_register_parent,
    api_login_parent,
    api_register_child,
    api_login_child,
    api_send_usage,
    api_get_usage,
)

# Android imports (safe on PC)
try:
    from jnius import autoclass, cast
    from android.permissions import request_permissions, Permission
    ANDROID = True
except Exception:
    ANDROID = False


class LoginScreen(Screen):
    pass


class ParentLoginScreen(Screen):
    family_key_label = StringProperty("")

    def do_login(self):
        email = self.ids.parent_email.text.strip()
        password = self.ids.parent_password.text.strip()
        if not email or not password:
            self.family_key_label = "Enter email and password"
            return

        # login or register parent
        key = api_login_parent(email, password)
        if key is None:
            key = api_register_parent(email, password)
            self.family_key_label = f"Registered. Family Key: {key}"
        else:
            self.family_key_label = f"Welcome back! Family Key: {key}"

        parent_screen = self.manager.get_screen("parent")
        parent_screen.parent_email = email
        parent_screen.family_key = key

        self.manager.current = "parent"


class ChildLoginScreen(Screen):
    status_msg = StringProperty("")

    def do_login(self):
        email = self.ids.child_email.text.strip()
        password = self.ids.child_password.text.strip()
        family_key = self.ids.family_key.text.strip()

        if not email or not password or not family_key:
            self.status_msg = "Fill all fields"
            return

        # login or register child
        existing_key = api_login_child(email, password)
        if existing_key is None:
            api_register_child(email, password, family_key)
            self.status_msg = "Registered and linked to family."
        else:
            if existing_key != family_key:
                self.status_msg = "Family key mismatch."
                return
            self.status_msg = "Login successful."

        # put info on child dashboard
        child_screen = self.manager.get_screen("child")
        child_screen.child_email = email
        child_screen.family_key = family_key

        # save config for background service
        base_dir = os.path.dirname(os.path.abspath(__file__))
        config_path = os.path.join(base_dir, "child_config.json")
        try:
            with open(config_path, "w", encoding="utf-8") as f:
                json.dump(
                    {
                        "child_email": email,
                        "family_key": family_key,
                    },
                    f,
                )
        except Exception as e:
            print("Failed to write child_config.json:", e)

        # start background service on Android
        if platform == "android":
            try:
                from jnius import autoclass
                PythonService = autoclass("org.kivy.android.PythonService")
                # 'screen_service' must match name in buildozer.spec
                PythonService.start("screen_service", "Screen Service")
            except Exception as e:
                print("Failed to start background service:", e)

        self.manager.current = "child"


class ChildScreen(Screen):
    child_email = StringProperty("")
    family_key = StringProperty("")
    usage_data = DictProperty({})

    def on_pre_enter(self):
        if ANDROID:
            Clock.schedule_interval(self.update_usage, 60)

    def on_leave(self):
        if ANDROID:
            Clock.unschedule(self.update_usage)

    def update_usage(self, *args):
        if ANDROID:
            from datetime import datetime, timedelta
            now = datetime.now()
            start = now - timedelta(hours=24)
            usage = get_usage_stats(start, now)
            self.usage_data = usage
        else:
            # fake data for PC testing
            self.usage_data = {
                "com.example.youtube": 5500,
                "com.example.chatapp": 3200,
                "com.example.browser": 9000,
            }

        grid = self.ids.usage_grid
        grid.clear_widgets()
        for pkg, seconds in self.usage_data.items():
            mins = str(seconds // 60)
            card = Factory.UsageCard(app_name=pkg, minutes=mins)
            grid.add_widget(card)

        # send to backend / fake backend
        if self.child_email:
            api_send_usage(self.child_email, self.usage_data)


class ParentScreen(Screen):
    parent_email = StringProperty("")
    family_key = StringProperty("")

    def load_child_usage(self):
        usage_by_child = api_get_usage(self.parent_email, self.family_key)

        grid = self.ids.parent_usage_grid
        grid.clear_widgets()

        if not usage_by_child:
            grid.add_widget(
                Factory.UsageCard(app_name="No data yet", minutes="0")
            )
            return

        for child_email, data in usage_by_child.items():
            usage_dict = data["usage"]
            heartbeat = data["heartbeat"]

            # header card per child
            grid.add_widget(
                Factory.UsageCard(
                    app_name=f"[Child] {child_email}",
                    minutes=f"Last seen: {heartbeat}",
                )
            )

            for pkg, seconds in usage_dict.items():
                mins = str(seconds // 60)
                card = Factory.UsageCard(
                    app_name=f"  {pkg}", minutes=f"{mins} min"
                )
                grid.add_widget(card)


class ScreenTimeApp(App):
    def build(self):
        if ANDROID:
            self.request_android_permissions()
        return Builder.load_file("screen_time.kv")

    def request_android_permissions(self):
        if not ANDROID:
            return
        request_permissions(
            [
                Permission.INTERNET,
                Permission.WRITE_EXTERNAL_STORAGE,
                Permission.READ_EXTERNAL_STORAGE,
                Permission.PACKAGE_USAGE_STATS,
            ]
        )


def get_usage_stats(start_dt, end_dt):
    if not ANDROID:
        return {}

    start_ms = int(start_dt.timestamp() * 1000)
    end_ms = int(end_dt.timestamp() * 1000)

    PythonActivity = autoclass("org.kivy.android.PythonActivity")
    UsageStatsManager = autoclass("android.app.usage.UsageStatsManager")
    Context = autoclass("android.content.Context")

    activity = PythonActivity.mActivity
    usm = cast(
        UsageStatsManager,
        activity.getSystemService(Context.USAGE_STATS_SERVICE)
    )

    interval_daily = UsageStatsManager.INTERVAL_DAILY
    usage_stats_list = usm.queryUsageStats(interval_daily, start_ms, end_ms)

    result = {}
    if usage_stats_list is None:
        return result

    for i in range(usage_stats_list.size()):
        stat = usage_stats_list.get(i)
        pkg = stat.getPackageName()
        seconds = int(stat.getTotalTimeInForeground() / 1000)
        if seconds > 0:
            result[pkg] = seconds

    return result


if __name__ == "__main__":
    ScreenTimeApp().run()
