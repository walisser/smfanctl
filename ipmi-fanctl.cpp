
#include <stdlib.h>
#include <stdio.h>
#include <unistd.h>
#include <string.h>

int main(int argc, char** argv)
{
    setreuid(0,0);

    if (getuid() != 0)
    {
        printf("%s must be run as root\n", argv[0]);
        return -1;
    }

    if (argc != 4)
    {
        printf("%s usage: -setpwm [zone] [percent]\n", argv[0]);
        return -2;
    }

    const char* mode = argv[1];
    if (strcmp(mode, "-setpwm") != 0)
    {
        printf("%s: invalid mode: %s\n", argv[0], mode);
        return -3;
    }

    int zone = atoi(argv[2]);
    int pwm = atoi(argv[3]);

    char cmd[1024]={0};
    snprintf(cmd, sizeof(cmd)-1, "ipmitool raw 0x30 0x70 0x66 0x01 0x%.02x 0x%.02x", zone, pwm);
    printf("%s\n", cmd);

    return system(cmd);
}
