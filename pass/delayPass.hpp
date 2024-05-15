#ifndef EBF_DELAY_PASS
#define EBF_DELAY_PASS

#include "llvm/Pass.h"
#include "llvm/IR/Function.h"
#include "llvm/Support/raw_ostream.h"
#include "llvm/IR/LegacyPassManager.h"
#include "llvm/Transforms/IPO/PassManagerBuilder.h"
#include "llvm/IR/Module.h"
#include "llvm/IR/IRBuilder.h"
#include "llvm/InitializePasses.h"
#include "llvm/Transforms/Utils/Local.h"
#include "llvm/IR/PassManager.h"

struct DelayPass : public llvm::FunctionPass
{
    static char ID;
    DelayPass() : llvm::FunctionPass(ID) {}

    /** @return whether the function `F` has changed */

    bool runOnFunction(llvm::Function &F) override
    {
        return injectDelays(F);
    }

protected:
    llvm::LLVMContext *Ctx;
    llvm::Function *currentFunction;
    std::string delayFunction = "_delay_function";
    std::string addThreadFunction = "add_thread";
    std::string joinThreadFunction = "join_thread";

    llvm::FunctionCallee addF;
    llvm::FunctionCallee joinF;
    llvm::FunctionCallee delayF;

    /** This flag control wether inject a delay or not*/
   // bool should_add_delay = true;
    void initializeEBFFunctions();

    /** @brief This function get the the callee function
     * @return the name of the function */
    llvm::StringRef getFunctionName(llvm::CallInst *callInst);

    /** @brief This function check for pthread_create and pthread_join functions, if they exists then 
     * we insert a call to insert a call to a function that count the active and release threads respectivally.
     * @return true if the call has been inserted*/
    bool instrumentThreadCounting(llvm::Instruction *I);
    
    /** @brief This function check for __VERIFIER_atomic functions, updating `should_add_delay` as needed.
     * @return true if the current instruction needs a delay after.*/
    
    bool shouldAddDelayInstruction(llvm::Instruction *I, bool &should_add_delay );
    /**  @brief this function will define a delay function to be instrumented.
     * It will iterate over all the instructions, instrumenting the delay as needed.
     * This function will insert a delay function and return true if the function was modified
     * @return whether the function `F` has changed */

    bool injectDelays(llvm::Function &F);

};

#endif // EBF_DELAY_PASS
