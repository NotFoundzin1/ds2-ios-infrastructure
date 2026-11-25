extern int probe_base_value(void);

int probe_plugin_value(void) {
    return probe_base_value() + 2;
}
