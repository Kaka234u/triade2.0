#include <stddef.h>
__attribute__((dllimport, ms_abi)) long long ShellExecuteW(void *, const wchar_t *, const wchar_t *, const wchar_t *, const wchar_t *, int);
int __attribute__((ms_abi)) start(void) {
    const wchar_t *url = L"https://triade2-0.onrender.com/";
    if (ShellExecuteW(NULL, L"open", L"msedge.exe", L"--app=https://triade2-0.onrender.com/", NULL, 1) > 32)
        return 0;
    return ShellExecuteW(NULL, L"open", url, NULL, NULL, 1) <= 32;
}
