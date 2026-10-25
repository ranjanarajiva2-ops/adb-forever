# adb-forever
get adb forever until you reboot by getting shizuku or adb onc

## Step 1: Turn on wireless debugging

You need either wifi or Shizuku for this. It stays on until you reboot.

With wifi: turn on wireless debugging and pair, then connect

With Shizuku: open rish or aShell You and run:

    while true; do settings put global adb_wifi_enabled 1; done

Then run ./adbscan.py and connect to each one use whichever works.

adbscan.py is required for the Shizuku method. It's in this repo.

## Step 2: Switch adb to port 5555

    adb tcpip 5555
    adb connect localhost:5555

All done. Now you can use adb with no wifi and no wireless debugging.

## Note

After every reboot, adb tcpip 5555 resets. Repeat both steps once.
