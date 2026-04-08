# Use baremodule to shave off a few KB from the serialized `.ji` file
baremodule ICU_jll
using Base
using Base: UUID
import JLLWrappers

JLLWrappers.@generate_main_file_header("ICU")
JLLWrappers.@generate_main_file("ICU", UUID("a51ab1cf-af8e-5615-a023-bc2c838bba6b"))
end  # module ICU_jll
