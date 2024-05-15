#include "MemoryTrackPass.hpp"
#include <llvm/Transforms/IPO/PassManagerBuilder.h>
#include <llvm/IR/LegacyPassManager.h>
#include <llvm/IR/DebugInfoMetadata.h>
#include <llvm/IR/Metadata.h>
#include <llvm/Support/raw_os_ostream.h>
#include <regex>
#include <vector>


/** This function iterate over the instructions in a basic block then, return pointer to the instruction */
inline llvm::Instruction *BBIteratorToInst(llvm::BasicBlock::iterator i)
{
  llvm::Instruction *pointer = reinterpret_cast<llvm::Instruction *>(&*i);
  return pointer;
}

void MemoryTrackPass::initializeEBFInstructions()
{
  llvm::Function &F = *this->currentFunction;
  /** pointer of void EBF_add_store_pointer(const char *var_name, int a, char *ptr,int b)*/
  /** int size 8 means char */
  this->EBF_pointer = F.getParent()->getOrInsertFunction(
      "EBF_add_store_pointer", llvm::Type::getVoidTy(*this->Ctx),
      llvm::Type::getInt8PtrTy(*this->Ctx), llvm::Type::getInt64Ty(*this->Ctx),
      llvm::Type::getInt8PtrTy(*this->Ctx), llvm::Type::getInt64Ty(*this->Ctx));

  this->EBF_pointer_fp = F.getParent()->getOrInsertFunction(
      "EBF_add_store_pointer_fp", llvm::Type::getVoidTy(*this->Ctx),
      llvm::Type::getInt8PtrTy(*this->Ctx), llvm::Type::getInt64Ty(*this->Ctx),
      llvm::Type::getInt8PtrTy(*this->Ctx), llvm::Type::getDoubleTy(*this->Ctx));
  /** getInt1PtrTy = void pointer*/
  this->EBF_pointer_ptr = F.getParent()->getOrInsertFunction(
      "EBF_add_store_pointer_ptr", llvm::Type::getVoidTy(*this->Ctx),
      llvm::Type::getInt8PtrTy(*this->Ctx), llvm::Type::getInt64Ty(*this->Ctx),
      llvm::Type::getInt8PtrTy(*this->Ctx), llvm::Type::getInt1PtrTy(*this->Ctx));

  // EBF_alloca(const char *var_name, const char *function_name, void *ptr)
  this->EBF_alloca = F.getParent()->getOrInsertFunction(
      "EBF_alloca", llvm::Type::getVoidTy(*this->Ctx),
      llvm::Type::getInt8PtrTy(*this->Ctx), llvm::Type::getInt8PtrTy(*this->Ctx), llvm::Type::getInt8PtrTy(*this->Ctx));

  this->EBFClosinFunction = F.getParent()->getOrInsertFunction("EBF_closing", llvm::Type::getVoidTy(*this->Ctx));

  this->EBF_exit = F.getParent()->getOrInsertFunction("__VERIFIER_exit", llvm::Type::getVoidTy(*this->Ctx));
}

void MemoryTrackPass::getDebugInfo()
{
  unsigned line_number;
  /** Return the debug location for this instruction*/
  llvm::DebugLoc location = this->currentInstruction->getDebugLoc();
  /** if we find an instruction with debugging information, then we get the line number */
  if (location)
  {
    /** Get line of this instruction */
    line_number = location.getLine();
  }
  else
  {
    line_number = 0;
  }
  /** Pass the values to the instruction */
  this->line_value =
      llvm::ConstantInt::getSigned(llvm::Type::getInt64Ty(*this->Ctx), line_number);
}

void MemoryTrackPass::runOnStoreInstruction()
{
  /** we are casting the store instruction by getting the address of the store operand and the value. (*var_address = receives)*/
  llvm::StoreInst *storeInst = llvm::dyn_cast<llvm::StoreInst>(&*this->currentInstruction);
  llvm::Value *var_address = storeInst->getPointerOperand();
  llvm::Value *receives = storeInst->getValueOperand();
  /** where we will instrument those functions, which is before each store instruction. */
  auto j = this->currentInstruction;
  llvm::IRBuilder<> builder(BBIteratorToInst(j));
  /** we check the type of receives*/
  auto is_float = receives->getType()->isFPOrFPVectorTy();
  auto is_ptr = receives->getType()->isPointerTy();
  /** we cast to a double unless its a float we then use another type of casting */
  llvm::Twine non_det("typecast_store_double");
  llvm::Value *pointerCast;
  /** Get the function call */
  llvm::FunctionCallee function_to_call;
  if (is_float)
  {
    pointerCast = llvm::CastInst::CreateFPCast(receives, llvm::Type::getDoubleTy(*this->Ctx),
                                               non_det, BBIteratorToInst(j));
    function_to_call = EBF_pointer_fp;
  }
  else if (is_ptr)
  {
    pointerCast = llvm::CastInst::CreateBitOrPointerCast(receives, llvm::Type::getInt1PtrTy(*this->Ctx),
                                                         non_det, BBIteratorToInst(j));
    function_to_call = EBF_pointer_ptr;
  }
  else
  {
    pointerCast = llvm::CastInst::CreateIntegerCast(receives, llvm::Type::getInt64Ty(*this->Ctx),
                                                    true, non_det, BBIteratorToInst(j));
    function_to_call = EBF_pointer;
  }

  /** Extract the Function and create a global string for it */
  llvm::Value *function_name_llvm =
      builder.CreateGlobalStringPtr(this->currentFunction->getName());
  /** we cast to a pointer */
  llvm::Twine ptr_cast("bitcast_EBF_ptr");
  llvm::Value *address_cast = llvm::CastInst::CreatePointerCast(
      var_address, llvm::Type::getInt8PtrTy(*this->Ctx), ptr_cast, BBIteratorToInst(j));
  /** Set the arguments for EBF_pointer */
  llvm::Value *args2[] = {address_cast, this->line_value, function_name_llvm, pointerCast};
  /** Create the call to EBF_pointer */
  builder.CreateCall(function_to_call, args2);
}

void MemoryTrackPass::instrumentAllocation() 
{
  llvm::AllocaInst *allocaInst = llvm::dyn_cast<llvm::AllocaInst>(&*this->currentInstruction);
  auto j = this->currentInstruction;
  j++;
  llvm::IRBuilder<> builder(BBIteratorToInst(j));
  llvm::Value *variable_name_llvm = builder.CreateGlobalStringPtr(allocaInst->getName());
    /** Extract the Function and create a global string for it (to save the variable name). */
  llvm::Value *function_name_llvm =
      builder.CreateGlobalStringPtr(this->currentFunction->getName());
  llvm::Twine non_det("bitcast_ebf");
  llvm::Value *pointerCast =llvm::CastInst::CreatePointerCast(
      allocaInst, llvm::Type::getInt8PtrTy(*this->Ctx), non_det, BBIteratorToInst(j));

  llvm::Value *args[] = {variable_name_llvm, function_name_llvm,pointerCast};
  builder.CreateCall(EBF_alloca, args);
}

void MemoryTrackPass::runOnCallInstruction(llvm::CallInst *callInst, llvm::LLVMContext *Ctx)
{

  /** We check the function name, if its not a function then we get the operand, if still null then return */
  llvm::Function *calleeFunction = callInst->getCalledFunction();

  if (calleeFunction == NULL)
  {
    /** Value* v = callInst->getCalledValue(); //FOR LLVM 10 */
    llvm::Value *v = callInst->getCalledOperand();
    calleeFunction = llvm::dyn_cast<llvm::Function>(v->stripPointerCasts());

    if (calleeFunction == NULL)
    {
      return;
    }
  }
  /** if the function == reach_error then we inject the EBF_closing function */
  if (calleeFunction->getName() == reachErrorFunction)
  {
    llvm::IRBuilder<> builder(callInst);
    builder.CreateCall(EBFClosinFunction);
  }

  /** we are looking for abort calls and add __verifier_exit before. */
  else if (calleeFunction->getName() == abortFunction)
  {
    llvm::IRBuilder<> builder(callInst);
    builder.CreateCall(EBF_exit);
  }
}


bool MemoryTrackPass::runOnFunction(llvm::Function &F)
{
  Ctx = &F.getContext();
  currentFunction = &F;
  initializeEBFInstructions();
  if (F.getName() == "main")
  {
    /** We get the current module for the function and iterate over all the global variables in this functions and save them into a vector.*/
    auto currentModule = F.getParent();
    std::vector<llvm::GlobalVariable *> globals;
    for (auto globalVar = currentModule->global_begin();
         globalVar != currentModule->global_end(); globalVar++)
    {
      llvm::GlobalVariable *variable = llvm::dyn_cast<llvm::GlobalVariable>(&*globalVar);
      /** llvm::errs() << "Hello with " << variable->getName(); */
      globals.push_back(variable);
    }

    /** we are injecting EBF_alloca with each global variable. */
    for (unsigned pos = 0; pos < globals.size(); pos++)
    {
      llvm::Function::iterator bb = this->currentFunction->begin();
      llvm::BasicBlock::iterator i = bb->begin();

      llvm::IRBuilder<> builder(BBIteratorToInst(i));
      llvm::GlobalVariable *variable = globals[pos];
      /** create a string to get the gloabal variable name */
      llvm::Value *name_llvm = builder.CreateGlobalStringPtr(variable->getName());
      llvm::Value *function_name_llvm =
      builder.CreateGlobalStringPtr(this->currentFunction->getName());
      /** we cast the variable address to a char pointer because EBF_alloca expect to receive a char pointer. */
      llvm::Twine non_det("bitcast_ebf");
      /** we cast the first argument in EBF_alloca. */
      llvm::Value *pointerCast = llvm::CastInst::CreatePointerCast(
          variable, llvm::Type::getInt8PtrTy(*this->Ctx), non_det, BBIteratorToInst(i));
      currentInstruction = i;
      /** We get the line from debug info. */
      getDebugInfo();
      /** we create the call of EBF_alloca, with all the arguments required. */
      llvm::Value *args[] = {name_llvm, function_name_llvm, pointerCast};
      builder.CreateCall(EBF_alloca, args);
    }
  }

  for (llvm::Function::iterator bb = F.begin(), e = F.end(); bb != e; ++bb)
  {
    for (llvm::BasicBlock::iterator i = bb->begin(), e = bb->end(); i != e; ++i)
    {
      currentInstruction = i;

      /** Found a Store Instruction */
      if (llvm::dyn_cast<llvm::StoreInst>(&*this->currentInstruction) != NULL)
      {
        getDebugInfo();
        runOnStoreInstruction();
      }
      /** Found a Allocation Instruction */
      if (llvm::dyn_cast<llvm::AllocaInst>(&*this->currentInstruction) != NULL) {
        getDebugInfo();
        instrumentAllocation();
      }
      if (llvm::CallInst *callInst = llvm::dyn_cast<llvm::CallInst>(&*i))
      {
        currentInstruction = i;
        runOnCallInstruction(callInst, &F.getContext());
      }
    }
  }
  return true;
}

char MemoryTrackPass::ID = 0;
static llvm::RegisterPass<MemoryTrackPass> X("memory_track",
                                             "Validate memory security proprieties using dynamic memory tracking");

// Automatically enable the pass.
static void registerMemoryTrackPass(const llvm::PassManagerBuilder &,
                                    llvm::legacy::PassManagerBase &PM)
{
  PM.add(new MemoryTrackPass());
}
static llvm::RegisterStandardPasses
    RegisterMyPass(llvm::PassManagerBuilder::EP_EarlyAsPossible,
                   registerMemoryTrackPass);
