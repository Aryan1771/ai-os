/* Test-only bridge to the unmodified upstream Plymouth script interpreter.
 * No daemon, renderer, keyboard, network or host configuration is used.
 */
#include <math.h>
#include <stdarg.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "ply-logger.h"
#include "script.h"
#include "script-execute.h"
#include "script-object.h"
#include "script-parse.h"

static int errors;
static int checks;

ply_logger_t *ply_logger_get_error_default(void) { return NULL; }

void ply_logger_inject_with_non_literal_format_string(ply_logger_t *logger,
                                                       const char *format, ...)
{
    (void) logger;
    va_list args;
    va_start(args, format);
    vfprintf(stderr, format, args);
    va_end(args);
    errors++;
}

static script_return_t check_value(script_state_t *state, void *unused)
{
    (void) unused;
    script_obj_t *value = script_obj_hash_get_element(state->local, "value");
    checks++;
    if (!script_obj_as_bool(value)) {
        char *label = script_obj_hash_get_string(state->local, "label");
        fprintf(stderr, "failed check: %s\n", label ? label : "unnamed");
        free(label);
        errors++;
    }
    script_obj_unref(value);
    return script_return_obj_null();
}

static script_return_t math_value(script_state_t *state, void *kind)
{
    double value = script_obj_hash_get_number(state->local, "value");
    /* script-lib-math.c binds Math.Int to floor, not truncation. */
    return script_return_obj(script_obj_new_number(kind ? sin(value) : floor(value)));
}

static script_return_t string_length(script_state_t *state, void *unused)
{
    (void) unused;
    char *text = script_obj_as_string(state->this);
    size_t length = text ? strlen(text) : 0;
    free(text);
    return script_return_obj(script_obj_new_number(length));
}

int main(int argc, char **argv)
{
    if (argc != 2) return 2;
    script_state_t *state = script_state_new(NULL);
    script_add_native_function(state->global, "Check", check_value, NULL,
                               "value", "label", NULL);
    script_obj_t *math = script_obj_new_hash();
    script_obj_hash_add_element(state->global, math, "Math");
    script_add_native_function(math, "Int", math_value, NULL, "value", NULL);
    script_add_native_function(math, "Sin", math_value, (void *) 1, "value", NULL);
    script_obj_unref(math);
    script_obj_t *strings = script_obj_new_hash();
    script_obj_hash_add_element(state->global, strings, "String");
    script_add_native_function(strings, "Length", string_length, NULL, NULL);
    script_obj_unref(strings);

    script_op_t *program = script_parse_file(argv[1]);
    if (!program || errors) return 1;
    script_return_t result = script_execute(state, program);
    script_obj_unref(result.object);
    if (result.type == SCRIPT_RETURN_TYPE_FAIL) errors++;
    script_state_destroy(state);
    script_parse_op_free(program);
    printf("checks=%d errors=%d\n", checks, errors);
    return errors || checks == 0;
}
