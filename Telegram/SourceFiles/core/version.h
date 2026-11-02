/*
This file is part of Telegram Desktop,
the official desktop application for the Telegram messaging service.

For license and copyright information please follow this link:
https://github.com/telegramdesktop/tdesktop/blob/master/LEGAL
*/
#pragma once

#include "base/const_string.h"

#define TDESKTOP_REQUESTED_ALPHA_VERSION (0ULL)

#ifdef TDESKTOP_ALLOW_CLOSED_ALPHA
#define TDESKTOP_ALPHA_VERSION TDESKTOP_REQUESTED_ALPHA_VERSION
#else // TDESKTOP_ALLOW_CLOSED_ALPHA
#define TDESKTOP_ALPHA_VERSION (0ULL)
#endif // TDESKTOP_ALLOW_CLOSED_ALPHA

// used in Updater.cpp and Setup.iss for Windows
// Custom server build: own GUID, so that this client has its own single
// instance, its own taskbar group and does not clash with official Telegram.
constexpr auto AppId = "{A7F3C2E1-9B4D-4E6A-8F1C-3D5B7A9E2C48}"_cs;
constexpr auto AppNameOld = "Telegram Win (Unofficial)"_cs;
// Custom server build: own data folder (%APPDATA%\PlumeGram Desktop), so the
// custom client never touches the session of an installed official Telegram.
constexpr auto AppName = "PlumeGram Desktop"_cs;
constexpr auto AppFile = "Telegram"_cs;
constexpr auto AppVersion = 7003004;
constexpr auto AppVersionStr = "7.3.4";
constexpr auto AppBetaVersion = true;
constexpr auto AppAlphaVersion = TDESKTOP_ALPHA_VERSION;
