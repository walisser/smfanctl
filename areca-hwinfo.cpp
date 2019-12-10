
#include <stdlib.h>
#include <stdio.h>
#include <unistd.h>
#include <string>

int main(int argc, char** argv)
{
    setreuid(0,0);

    if (getuid() != 0)
    {
       printf("%s must be run as root\n", argv[0]);
       return -1;
    }

    if (argc > 1 && std::string(argv[1])=="-disk-info")
       return system("./cli64 disk info");
    if (argc > 1 && std::string(argv[1])=="-disk-smart")
    {
       std::string cmd = "echo -e \"";
       for (int i = 0; i < argc; i++)
       {
          cmd += "disk smart drv=";
          cmd += argv[i];
          cmd += "\n";
       }
       cmd += "exit";
       cmd += "\" | ./cli64";
       return system(cmd.c_str());
    }

    return system("./cli64 hw info");
}
