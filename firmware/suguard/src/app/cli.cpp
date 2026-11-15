#include "cli.h"

#include <stdio.h>
#include <string.h>

namespace {

void out(const SgCliHooks* h, const char* s) {
  if (h->print) h->print(h->ctx, s);
}

// Splits off the next space-separated token; returns NULL at the end.
char* next_token(char** p) {
  char* s = *p;
  while (*s == ' ' || *s == '\t') s++;
  if (*s == '\0') return nullptr;
  char* start = s;
  while (*s && *s != ' ' && *s != '\t') s++;
  if (*s) *s++ = '\0';
  *p = s;
  return start;
}

// The rest of the line without leading/trailing blanks (may contain spaces).
char* rest(char* s) {
  while (*s == ' ' || *s == '\t') s++;
  size_t n = strlen(s);
  while (n && (s[n - 1] == ' ' || s[n - 1] == '\t' || s[n - 1] == '\r' || s[n - 1] == '\n')) s[--n] = '\0';
  return s;
}

void set_and_report(SgConfig* cfg, const SgCliHooks* h, const char* key, const char* value) {
  char msg[96];
  char err[64] = "";
  if (!sg_config_set(cfg, key, value, err, sizeof err)) {
    snprintf(msg, sizeof msg, "error: %s: %s\n", key, err);
    out(h, msg);
    return;
  }
  char shown[160];
  sg_config_get(cfg, key, shown, sizeof shown, false);
  snprintf(msg, sizeof msg, "ok %s = ", key);
  out(h, msg);
  out(h, shown);
  out(h, "  (not saved yet: type 'save')\n");
  if (h->apply) h->apply(h->ctx);
}

void show_all(const SgConfig* cfg, const SgCliHooks* h) {
  for (int i = 0; sg_config_key(i); i++) {
    char value[160], line[240];
    sg_config_get(cfg, sg_config_key(i), value, sizeof value, false);
    snprintf(line, sizeof line, "  %-18s %-28s # %s\n", sg_config_key(i), value, sg_config_help(i));
    out(h, line);
  }
}

const char kHelp[] =
    "SuGuard bracelet console\n"
    "  status                 sensor, battery, Wi-Fi and last readings\n"
    "  get [key]              show settings\n"
    "  set <key> <value>      change a setting (then 'save')\n"
    "  wifi <ssid> [password] set the Wi-Fi network\n"
    "  user <email>           account e-mail used in the SuGuard app\n"
    "  stream on|off          print raw PPG windows on USB (for the PC tools)\n"
    "  led red|ir|both|off    light one LED for 5 s (red must be visible; if not: set swap_red_ir 1)\n"
    "  mark [text]            store an event marker (e.g. a fingerstick)\n"
    "  save                   store settings in flash\n"
    "  defaults               restore factory settings (then 'save')\n"
    "  reboot\n";

}  // namespace

void sg_cli_handle(char* line, SgConfig* cfg, const SgCliHooks* h) {
  char* p = line;
  char* cmd = next_token(&p);
  if (!cmd) return;

  if (strcmp(cmd, "help") == 0 || strcmp(cmd, "?") == 0) {
    out(h, kHelp);
  } else if (strcmp(cmd, "status") == 0) {
    if (h->status) h->status(h->ctx);
  } else if (strcmp(cmd, "get") == 0) {
    char* key = next_token(&p);
    if (!key) {
      show_all(cfg, h);
      return;
    }
    char value[160];
    if (sg_config_get(cfg, key, value, sizeof value, false)) {
      out(h, value);
      out(h, "\n");
    } else {
      out(h, "error: unknown key\n");
    }
  } else if (strcmp(cmd, "set") == 0) {
    char* key = next_token(&p);
    if (!key) {
      out(h, "usage: set <key> <value>\n");
      return;
    }
    set_and_report(cfg, h, key, rest(p));
  } else if (strcmp(cmd, "wifi") == 0) {
    char* ssid = next_token(&p);
    if (!ssid) {
      out(h, "usage: wifi <ssid> [password]   (use 'set wifi_ssid ...' for names with spaces)\n");
      return;
    }
    char* pass = rest(p);
    set_and_report(cfg, h, "wifi_ssid", ssid);
    set_and_report(cfg, h, "wifi_pass", pass);
  } else if (strcmp(cmd, "user") == 0) {
    set_and_report(cfg, h, "user", rest(p));
  } else if (strcmp(cmd, "stream") == 0) {
    set_and_report(cfg, h, "stream_raw", rest(p));
  } else if (strcmp(cmd, "led") == 0) {
    const char* what = rest(p);
    uint8_t mode;
    if (strcmp(what, "red") == 0) mode = 1;
    else if (strcmp(what, "ir") == 0) mode = 2;
    else if (strcmp(what, "both") == 0) mode = 3;
    else if (strcmp(what, "off") == 0) mode = 0;
    else {
      out(h, "usage: led red|ir|both|off\n");
      return;
    }
    out(h, h->led_test && h->led_test(h->ctx, mode) ? "ok (5 s)\n" : "error: sensor busy or missing\n");
  } else if (strcmp(cmd, "mark") == 0) {
    if (h->mark) h->mark(h->ctx, rest(p));
    out(h, "ok\n");
  } else if (strcmp(cmd, "save") == 0) {
    if (h->save) h->save(h->ctx);
  } else if (strcmp(cmd, "defaults") == 0) {
    sg_config_defaults(cfg);
    out(h, "factory settings restored in RAM (type 'save' to keep them)\n");
    if (h->apply) h->apply(h->ctx);
  } else if (strcmp(cmd, "reboot") == 0) {
    if (h->reboot) h->reboot(h->ctx);
  } else {
    out(h, "unknown command, type 'help'\n");
  }
}
