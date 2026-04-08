# Use baremodule to shave off a few KB from the serialized `.ji` file
baremodule dlfcn_win32_jll
using Base
using Base: UUID
import JLLWrappers

JLLWrappers.@generate_main_file_header("dlfcn_win32")
JLLWrappers.@generate_main_file("dlfcn_win32", UUID("c4b69c83-5512-53e3-94e6-de98773c479f"))
end  # module dlfcn_win32_jll
