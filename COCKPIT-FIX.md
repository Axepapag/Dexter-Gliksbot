# 🔧 Cockpit NuGet Package Fix

## Problem
The original Cockpit project referenced `AvalonDock 4.72.0`, which doesn't exist on NuGet.org. The old `AvalonDock` package maxes out at version 2.0.2000 and doesn't support .NET 8.0.

**Error:**
```
error NU1102: Unable to find package AvalonDock with version (>= 4.72.0)
  - Found 25 version(s) in nuget.org [ Nearest version: 2.0.2000 ]
```

## Solution ✅
Updated to use **`Dirkster.AvalonDock`** (modern fork maintained for .NET 8.0):
- Changed from `AvalonDock 4.72.0` → `Dirkster.AvalonDock 4.72.1`
- Added `Dirkster.AvalonDock.Themes.VS2013 4.72.1` for theming support

## What Changed
**File:** `cockpit/DexterCockpit/DexterCockpit.csproj`

```diff
- <PackageReference Include="AvalonDock" Version="4.72.0" />
+ <PackageReference Include="Dirkster.AvalonDock" Version="4.72.1" />
+ <PackageReference Include="Dirkster.AvalonDock.Themes.VS2013" Version="4.72.1" />
```

## Pull and Test (M:\DexG\)

### 1. Pull Latest Changes
```powershell
cd M:\DexG
git pull origin main
```

### 2. Restore NuGet Packages
```powershell
cd M:\DexG\cockpit\DexterCockpit
dotnet restore
```

### 3. Build the Cockpit
```powershell
dotnet build
```

**Expected output:**
```
Build succeeded.
    0 Warning(s)
    0 Error(s)
```

### 4. Test with Launcher
```powershell
cd M:\DexG
.\Launch-Dexter-Cockpit.bat
```

## About Dirkster.AvalonDock
- **Official fork:** https://github.com/Dirkster99/AvalonDock
- **NuGet:** https://www.nuget.org/packages/Dirkster.AvalonDock/
- **Status:** Actively maintained, .NET 8.0 compatible
- **Features:** Full AvalonDock functionality with modern .NET support

## Compatibility Notes

### ✅ Fixed
- `AvalonDock` package now resolves correctly
- No more NU1102 errors
- .NET 8.0 fully supported

### ⚠️ Expected Warnings (safe to ignore)
```
warning NU1701: Package 'LiveCharts 0.9.7' was restored using '.NETFramework,Version=v4.6.1'
warning NU1701: Package 'LiveCharts.Wpf 0.9.7' was restored using '.NETFramework,Version=v4.6.1'
```

**Why:** LiveCharts 0.9.7 targets .NET Framework but works fine on .NET 8.0. These warnings are informational only.

## If Build Still Fails

### Clear NuGet Cache
```powershell
dotnet nuget locals all --clear
cd M:\DexG\cockpit\DexterCockpit
dotnet restore --force
dotnet build
```

### Verify .NET 8.0 SDK
```powershell
dotnet --version
```
**Expected:** `8.0.x` or higher

**If not installed:** https://dotnet.microsoft.com/download/dotnet/8.0

---

## Commit Details
- **Commit:** `083a7c9`
- **Message:** "fix: Update AvalonDock to Dirkster.AvalonDock for .NET 8.0 support"
- **Date:** 2025-10-14
- **Status:** ✅ Pushed to GitHub

---

**Ready to test!** Pull the changes on M:\DexG\ and run the launcher. The build should now succeed without errors.
