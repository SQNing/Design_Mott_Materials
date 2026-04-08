# Use baremodule to shave off a few KB from the serialized `.ji` file
baremodule cif_api_jll
using Base
using Base: UUID
import JLLWrappers

JLLWrappers.@generate_main_file_header("cif_api")
JLLWrappers.@generate_main_file("cif_api", UUID("6fcef0ae-1c05-5fc1-b206-1cf994addbad"))
end  # module cif_api_jll
