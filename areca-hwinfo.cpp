
#include <stdlib.h>
#include <stdio.h>
#include <unistd.h>

int main(int argc, char** argv)
{
    setreuid(0,0);

    if (getuid() != 0)
    {
       printf("%s must be run as root\n", argv[0]);
       return -1;
    }

    return system("./cli64 hw info");
}
