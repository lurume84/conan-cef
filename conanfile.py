from conans import ConanFile, CMake, tools
import os


class CEFConan(ConanFile):
    name = "cef"
    version = "3.3626.1881.g628f810"
    description = "The Chromium Embedded Framework (CEF) is an open source framework for embedding a web browser engine which is based on the Chromium core"
    topics = ("conan", "cef", "chromium", "chromium-embedded-framework")
    url = "https://github.com/lurume84/conan-cef"
    homepage = "https://bitbucket.org/chromiumembedded/cef"
    license = "BSD-3Clause"
    exports = ["LICENSE.md"]
    exports_sources = ["CMakeLists.txt"]
    generators = "cmake"

    settings = "os", "compiler", "build_type", "arch"
    options = {
        "use_sandbox": [True, False],
        "debug_info_flag_vs": ["-Zi", "-Z7"]
    }
    default_options = {
        'use_sandbox': False,
        'debug_info_flag_vs': '-Z7'
    }

    _source_subfolder = "source_subfolder"
    _build_subfolder = "build_subfolder"

    def get_cef_distribution_name(self):
        platform = ""
        if self.settings.os == "Windows":
            platform = "windows"
        if self.settings.os == "Macos":
            platform = "macosx"
            platform = "macosx"
        if self.settings.os == "Linux":
            platform = "linux"
        if self.settings.arch == "x86":
            platform += "32"
        else:
            platform += "64"
        return "cef_binary_%s_%s" % (self.version, platform)

    # def config(self):
        # if self.settings.os == "Windows" and self.settings.compiler == "Visual Studio" and self.settings.compiler.version != "14":
            # self.options.remove("use_sandbox") # it requires to be built with that exact version for sandbox support

    def source(self):
        self.output.info("Downloading CEF prebuilts from opensource.spotify.com/cefbuilds/index.html")

        cef_download_filename ="{}.tar.bz2".format(self.get_cef_distribution_name())
        archive_url = "http://opensource.spotify.com/cefbuilds/{}".format(cef_download_filename)
        tools.get(archive_url)
        os.rename(self.get_cef_distribution_name(), self._source_subfolder)

        cmake_vars_file = "{}/cmake/cef_variables.cmake".format(self._source_subfolder)
        if self.settings.compiler == "Visual Studio" and not (self.settings.compiler.runtime == "MT" or self.settings.compiler.runtime == "MTd"):
            tools.replace_in_file(cmake_vars_file, "/MT           # Multithreaded release runtime", "/MD           # Multithreaded release runtime")
            tools.replace_in_file(cmake_vars_file, "/MDd          # Multithreaded debug runtime", "/MDd          # Multithreaded debug runtime")

        #
        # Clang Patch, for Linux & MacOS (should be theoretically not necessary with CEF >= 2987)
        #
        if self.settings.compiler == "clang":
            tools.replace_in_file(cmake_vars_file, 'include(CheckCXXCompilerFlag)', """include(CheckCXXCompilerFlag)

              CHECK_CXX_COMPILER_FLAG(-Wno-undefined-var-template COMPILER_SUPPORTS_NO_UNDEFINED_VAR_TEMPLATE)
              if(COMPILER_SUPPORTS_NO_UNDEFINED_VAR_TEMPLATE)
                list(APPEND CEF_CXX_COMPILER_FLAGS
                  -Wno-undefined-var-template   # Don't warn about potentially uninstantiated static members
                  )
            endif()""")

        tools.replace_in_file(cmake_vars_file, 'set(CEF_DEBUG_INFO_FLAG "/Zi"', 'set(CEF_DEBUG_INFO_FLAG "{}"'.format(self.options.debug_info_flag_vs))

    def system_requirements(self):
        if self.settings.os == "Linux" and tools.os_info.is_linux:
            if tools.os_info.with_apt:
                installer = tools.SystemPackageTool()
                if self.settings.arch == "x86":
                    arch_suffix = ':i386'
                elif self.settings.arch == "x86_64":
                    arch_suffix = ':amd64'

                packages = ['libpangocairo-1.0-0{}'.format(arch_suffix)]
                packages.append('libxcomposite1{}'.format(arch_suffix))
                packages.append('libxrandr2{}'.format(arch_suffix))
                packages.append('libxcursor1{}'.format(arch_suffix))
                packages.append('libatk1.0-0{}'.format(arch_suffix))
                packages.append('libcups2{}'.format(arch_suffix))
                packages.append('libnss3{}'.format(arch_suffix))
                packages.append('libgconf-2-4{}'.format(arch_suffix))
                packages.append('libxss1{}'.format(arch_suffix))
                packages.append('libasound2{}'.format(arch_suffix))
                packages.append('libxtst6{}'.format(arch_suffix))
                packages.append('libgtk2.0-dev{}'.format(arch_suffix))
                packages.append('libgdk-pixbuf2.0-dev{}'.format(arch_suffix))
                packages.append('freeglut3-dev{}'.format(arch_suffix))

                for package in packages:
                    installer.install(package)

    def _configure_cmake(self):
        cmake = CMake(self)
        cmake.definitions["CEF_ROOT"] = self._source_subfolder
        cmake.definitions["USE_SANDBOX"] = "ON" if self.options.use_sandbox else "OFF"

        cmake.configure(build_folder=self._build_subfolder)
        return cmake

    def build(self):
        cmake = self._configure_cmake()
        cmake.build()

    def package(self):
        cmake = self._configure_cmake()
        cmake.install()

        # Copy headers
        self.copy('*', dst='include/include', src='{}/include'.format(self._source_subfolder))

        # Copy all stuff from the Debug/Release folders in the downloaded cef bundle:
        dis_folder = "{}/{}".format(self._source_subfolder, self.settings.build_type)
        res_folder = "{}/Resources".format(self._source_subfolder)
        # resource files: taken from cmake/cef_variables (on macosx we would need to convert the COPY_MACOSX_RESOURCES() function)
        cef_resources = ["cef.pak", "cef_100_percent.pak", "cef_200_percent.pak", "cef_extensions.pak", "devtools_resources.pak", "icudtl.dat", "locales*"]
        for res in cef_resources:
            self.copy(res, dst="bin", src=res_folder, keep_path=True)

        if self.settings.os == "Linux":
            # CEF binaries: (Taken from cmake/cef_variables)
            self.copy("libcef.so", dst="lib", src=dis_folder, keep_path=False)
            self.copy("natives_blob.bin", dst="bin", src=dis_folder, keep_path=False)
            self.copy("snapshot_blob.bin", dst="bin", src=dis_folder, keep_path=False)
            self.copy("v8_context_snapshot.bin", dst="bin", src=dis_folder, keep_path=False)
            if self.options.use_sandbox:
                self.copy("chrome-sandbox", dst="bin", src=dis_folder, keep_path=False)
            self.copy("*cef_dll_wrapper.a", dst="lib", keep_path=False)
        if self.settings.os == "Windows":
            # CEF binaries: (Taken from cmake/cef_variables)
            self.copy("*.dll", dst="bin", src=dis_folder)
            self.copy("libcef.lib", dst="lib", src=dis_folder, keep_path=False)
            self.copy("natives_blob.bin", dst="bin", src=dis_folder, keep_path=False)
            self.copy("snapshot_blob.bin", dst="bin", src=dis_folder, keep_path=False)
            self.copy("v8_context_snapshot.bin", dst="bin", src=dis_folder, keep_path=False)
            if self.options.use_sandbox:
                self.copy("cef_sandbox.lib", dst="lib", src=dis_folder, keep_path=False)
            self.copy("*cef_dll_wrapper.lib", dst="lib", keep_path=False)  # libcef_dll_wrapper is somewhere else

    def package_info(self):
        if self.settings.compiler == "Visual Studio":
            self.cpp_info.libs = ["libcef_dll_wrapper", "libcef"]
        else:
            self.cpp_info.libs = ["cef_dll_wrapper", "cef"]
            self.cpp_info.defines += ["_FILE_OFFSET_BITS=64"]

        if self.options.use_sandbox:
            if self.settings.os == "Windows":
                self.cpp_info.libs += ["cef_sandbox", "dbghelp", "psapi", "version", "winmm"]
            self.cpp_info.defines += ["USE_SANDBOX", "CEF_USE_SANDBOX", "PSAPI_VERSION=1"]
        if self.settings.os == "Windows":
            self.cpp_info.libs += ["glu32", "opengl32", "comctl32", "rpcrt4", "shlwapi", "ws2_32"]
