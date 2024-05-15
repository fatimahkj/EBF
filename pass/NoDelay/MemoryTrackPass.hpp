#ifndef MODULES_BACKEND_PASS_MEMORYTRACKPASS_HPP_
#define MODULES_BACKEND_PASS_MEMORYTRACKPASS_HPP_

#include <llvm/IR/Constants.h>
#include <llvm/IR/Function.h>
#include <llvm/IR/IRBuilder.h>
#include <llvm/IR/Instructions.h>
#include <llvm/IR/Metadata.h>
#include <llvm/IR/Module.h>
#include <llvm/Pass.h>
#include <llvm/Support/raw_ostream.h>
#include <iostream>
#include <sstream>
#include <stdexcept>
#include <string>
#include <vector>

struct MemoryTrackPass : public llvm::FunctionPass
{
    /** @brief  This function check the entry point of program,
     *  it get the global variables for each module and inject EBF_alloca
     * @return the call of all the functions we defined in the program
     */
    static char ID;
    explicit MemoryTrackPass() : llvm::FunctionPass(ID) {}
    bool runOnFunction(llvm::Function &F);

protected:
    llvm::LLVMContext *Ctx;
    llvm::Function *currentFunction;
    llvm::ConstantInt *line_value;
    llvm::ConstantInt *scope_value;
    std::string reachErrorFunction = "reach_error";
    std::string abortFunction = "abort";
    llvm::FunctionCallee EBFClosinFunction = NULL;
    llvm::BasicBlock::iterator currentInstruction;


    llvm::FunctionCallee EBF_pointer;
    llvm::FunctionCallee EBF_pointer_fp;
    llvm::FunctionCallee EBF_pointer_ptr;
    llvm::FunctionCallee EBF_alloca;
    llvm::FunctionCallee EBF_exit;


    /**=-=-=-=--=-=-=-=-=-=-=-=--=-=-=-=-=-=-=-=--=-=-=-=-=-=-=-=--=-=-=-=-=-=-=-=--=-=-=-=-*/
    /** @brief This function will initialize the types of all the functions
     *  that we will insert to track information.
     */
    void initializeEBFInstructions();
    /**=-=-=-=--=-=-=-=-=-=-=-=--=-=-=-=-=-=-=-=--=-=-=-=-=-=-=-=--=-=-=-=-=-=-=-=--=-=-=-=-*/

    /**=-=-=-=--=-=-=-=-=-=-=-=--=-=-=-=-=-=-=-=--=-=-=-=-=-=-=-=--=-=-=-=-=-=-=-=--=-=-=-=-*/
    /** @brief This function get the line number from debugging information
     * The line value will be initialized with the current instruction
    */
    void getDebugInfo();
    /**=-=-=-=--=-=-=-=-=-=-=-=--=-=-=-=-=-=-=-=--=-=-=-=-=-=-=-=--=-=-=-=-=-=-=-=--=-=-=-=-*/


    /**=-=-=-=--=-=-=-=-=-=-=-=--=-=-=-=-=-=-=-=--=-=-=-=-=-=-=-=--=-=-=-=-=-=-=-=--=-=-=-=-*/
    /** @brief This function will instrument the functions (EBF_pointer_*) 
     * and insert them before each store instruction
     */
    void runOnStoreInstruction();
    /**=-=-=-=--=-=-=-=-=-=-=-=--=-=-=-=-=-=-=-=--=-=-=-=-=-=-=-=--=-=-=-=-=-=-=-=--=-=-=-=-*/


    /**=-=-=-=--=-=-=-=-=-=-=-=--=-=-=-=-=-=-=-=--=-=-=-=-=-=-=-=--=-=-=-=-=-=-=-=--=-=-=-=-*/
    /** @brief This function checks for reach_error and abort function and instrument them,
     * by injecting EBF_closing and __VERIFIER_exit functions.
     */
    void runOnCallInstruction(llvm::CallInst *callInst, llvm::LLVMContext *Ctx);
    /**=-=-=-=--=-=-=-=-=-=-=-=--=-=-=-=-=-=-=-=--=-=-=-=-=-=-=-=--=-=-=-=-=-=-=-=--=-=-=-=-*/


    /**=-=-=-=--=-=-=-=-=-=-=-=--=-=-=-=-=-=-=-=--=-=-=-=-=-=-=-=--=-=-=-=-=-=-=-=--=-=-=-=-*/
    /** @brief This function get the variable name and prepare the arguments and inject EBF_alloca function
     */
    void instrumentAllocation();
    /**=-=-=-=--=-=-=-=-=-=-=-=--=-=-=-=-=-=-=-=--=-=-=-=-=-=-=-=--=-=-=-=-=-=-=-=--=-=-=-=-*/



};

#endif // MODULES_BACKEND_PASS_MEMORYTRACKPASS_HPP_
